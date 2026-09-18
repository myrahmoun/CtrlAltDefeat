import grpc
import uuid
import queue
import threading
from concurrent import futures

from src.game import Game, GameStats
from src.player import Player as GamePlayer
from src.cards import ActionCard, GlitchCard
from proto import basic_pb2 as pb
from proto import basic_pb2_grpc as pb_grpc

# ── Registry ──────────────────────────────────────────────────────────────
# _registry_lock protects only the three dicts below (creating/looking up
# entries) — it is never held during actual game logic. Each game has its
# own lock in _game_locks, acquired only for that game's mutations, so
# unrelated games never block each other.

_games: dict[str, Game] = {}
_game_locks: dict[str, threading.Lock] = {}
_watchers: dict[str, list[queue.Queue]] = {}
_registry_lock = threading.Lock()


def _get_game_and_lock(game_id, context):
    """Look up a game and its lock, aborting with NOT_FOUND if missing."""
    with _registry_lock:
        game = _games.get(game_id)
        lock = _game_locks.get(game_id)
    if not game:
        context.abort(grpc.StatusCode.NOT_FOUND, f"Game {game_id} not found")
    return game, lock


def _find_player(game: Game, player_id: str, context=None) -> GamePlayer:
    """
    Look up a player in a game. Given a context, aborts the RPC with
    NOT_FOUND rather than raising, so an unknown player id reaches the
    client as a real status code instead of leaking as UNKNOWN.
    """
    for p in game.players:
        if p.id == player_id:
            return p
    if context is not None:
        context.abort(
            grpc.StatusCode.NOT_FOUND, f"Player {player_id} not found in game {game.id}"
        )
    raise KeyError(f"Player {player_id} not found in game {game.id}")


def _current_player(game: Game):
    """
    The player whose turn it is, or None if the game isn't running or has
    nobody left in it. Guards Game.get_current_player(), which indexes
    turn_order directly and so raises IndexError once players start leaving.
    """
    if game.status != GameStats.PLAYING or not game.turn_order:
        return None
    if game.current_turn_index >= len(game.turn_order):
        return None
    return game.turn_order[game.current_turn_index]


def _require_turn(game: Game, player: GamePlayer, context) -> None:
    """Abort unless the game is in progress and it is this player's turn."""
    if game.status != GameStats.PLAYING:
        context.abort(grpc.StatusCode.FAILED_PRECONDITION, "Game is not in progress")
    current = _current_player(game)
    if current is None or current.id != player.id:
        context.abort(grpc.StatusCode.FAILED_PRECONDITION, "It is not your turn")


def _remove_player(game: Game, player: GamePlayer) -> None:
    """
    Take a player out of a game, keeping current_turn_index pointing at
    whoever it pointed at before wherever that's still possible.

    Game.turn_order is a plain list indexed by current_turn_index, so
    removing an entry shifts every later index down. Removing a player
    without fixing the index either skips the next player's turn or, if the
    leaver was last in turn order, leaves the index past the end of the
    list — which makes get_current_player() raise IndexError on every
    subsequent call and leaves the game unrecoverable for everyone still in
    it.
    """
    current = _current_player(game)

    if player in game.turn_order:
        index = game.turn_order.index(player)
        game.turn_order.remove(player)
        if current is player:
            # Their turn goes with them: play passes to whoever now
            # occupies the slot they vacated, wrapping if they were last.
            game.current_turn_index = index % len(game.turn_order) if game.turn_order else 0
        elif current is not None:
            # Somebody else is mid-turn — keep the index pointing at them.
            game.current_turn_index = game.turn_order.index(current)

    if player in game.players:
        game.players.remove(player)


def _discard_empty_game(game_id: str) -> None:
    """
    Drop a game from the registry once its last player has left, so
    abandoned games don't accumulate. A freshly created game that nobody
    has joined yet never reaches here, since only player removal calls it.
    """
    with _registry_lock:
        game = _games.get(game_id)
        if game is None or game.players or _watchers.get(game_id):
            return
        _games.pop(game_id, None)
        _game_locks.pop(game_id, None)
        _watchers.pop(game_id, None)
    print(f"[server] Game {game_id} is empty — removed")


_REQUIRED_CATEGORIES = ("Intelligence", "Technology", "Governance", "Cybersecurity")


def _validate_operation(player: GamePlayer, objective_index: int, action_indices: list) -> str:
    """
    Vet a proposed operation before it reaches Game.execute_turn, returning
    an error message, or "" if it's well formed.

    Game._execute_operation discards the four played cards *before*
    evaluating them, so an operation that turns out to be malformed costs
    the player those cards for nothing and then raises
    InvalidOperationException — which no servicer catches, so it also
    reaches the client as UNKNOWN. Rejecting it up front leaves the hand
    untouched and returns a real status code. The client's HandWidget
    already enforces the same shape; this makes the server stop trusting it.
    """
    hand = player.hand
    if not 0 <= objective_index < len(hand.objective_cards):
        return f"No objective card at index {objective_index}"
    if len(action_indices) != 4:
        return f"An operation needs exactly 4 action cards, got {len(action_indices)}"
    if len(set(action_indices)) != 4:
        return "Cannot play the same action card twice in one operation"
    for i in action_indices:
        if not 0 <= i < len(hand.non_objective_cards):
            return f"No action card at index {i}"

    cards = [hand.non_objective_cards[i] for i in action_indices]
    glitches = [c.name for c in cards if isinstance(c, GlitchCard)]
    if glitches:
        return f"Glitch Cards cannot be played into an operation: {', '.join(glitches)}"

    # ActionCard.category is a plain str for cards loaded from JSON but a
    # CardCategory for cards built directly, and str(CardCategory.X) gives
    # "CardCategory.X", not its value — so normalise via .value.
    categories = sorted(getattr(c.category, "value", c.category) for c in cards)
    if categories != sorted(_REQUIRED_CATEGORIES):
        return (
            "An operation needs exactly one card of each category "
            f"({', '.join(_REQUIRED_CATEGORIES)}); got {', '.join(categories)}"
        )
    return ""


def _non_objective_card_to_proto(c) -> pb.NonObjectiveCard:
    """Build the oneof-wrapped proto card, branching on which subclass c actually is."""
    if isinstance(c, ActionCard):
        return pb.NonObjectiveCard(
            name=c.name, description=c.description,
            action=pb.ActionCard(
                category=c.category, responsibility=c.responsibility, effect=c.effect,
            ),
        )
    elif isinstance(c, GlitchCard):
        return pb.NonObjectiveCard(
            name=c.name, description=c.description,
            glitch=pb.GlitchCard(
                glitch_type=c.glitchType,
                effect_type=c.effect_type.value,
                target_category=c.target_category.value if c.target_category else "",
                count=c.count,
            ),
        )
    raise TypeError(f"Unknown non-objective card type: {type(c)!r}")


def _to_proto_state(game: Game) -> pb.GameState:
    """Convert internal Game object to proto GameState."""
    current = _current_player(game)
    return pb.GameState(
        game_id=game.id,
        status=game.status.name.lower(),
        current_player_id=current.id if current else "",
        winner_id=game.winner.id if game.winner else "",
        players=[pb.Player(
            id=p.id,
            name=p.name,
            board_position=p.board_position,
            lose_next_turn=p.lose_next_turn,
            hand=pb.Hand(
                non_objective_cards=[_non_objective_card_to_proto(c) for c in p.hand.non_objective_cards],
                objective_cards=[pb.ObjectiveCard(
                    name=c.name, description=c.description,
                    responsibility=c.responsibility, effect=c.effect,
                ) for c in p.hand.objective_cards],
            ),
            **({"pending_discard": p.pending_discard} if p.pending_discard else {}),
        ) for p in game.players],
    )


def _broadcast(game_id: str, game: Game) -> pb.GameState:
    """Push the current state to every watcher of this game. Caller must hold the game's lock."""
    state = _to_proto_state(game)
    for q in _watchers.get(game_id, []):
        q.put(state)
    return state


# ── Servicers ─────────────────────────────────────────────────────────────

class LobbyServicer(pb_grpc.LobbyServicer):

    def CreateGame(self, request, context):
        game_id = str(uuid.uuid4())[:8]
        with _registry_lock:
            _games[game_id] = Game(game_id)
            _game_locks[game_id] = threading.Lock()
            _watchers[game_id] = []
        print(f"[server] Game created: {game_id}")
        game, lock = _get_game_and_lock(game_id, context)
        with lock:
            return _to_proto_state(game)

    def JoinGame(self, request, context):
        game, lock = _get_game_and_lock(request.game_id, context)
        with lock:
            if any(p.name == request.player_name for p in game.players):
                context.abort(grpc.StatusCode.ALREADY_EXISTS, f"Name '{request.player_name}' is already taken")
            player = GamePlayer(request.player_name)
            game.players.append(player)
            print(f"[server] {player.name} joined {game.id}")
            return pb.JoinResponse(player_id=player.id, state=_broadcast(game.id, game))

    def StartGame(self, request, context):
        game, lock = _get_game_and_lock(request.game_id, context)
        with lock:
            if game.status != GameStats.LOBBY:
                return _to_proto_state(game)
            try:
                game.setup_game()
            except ValueError as e:
                # Too few or too many players — the caller can fix this, so
                # it needs a real status code rather than leaking as UNKNOWN.
                context.abort(grpc.StatusCode.FAILED_PRECONDITION, str(e))
            print(f"[server] Game {game.id} started")
            return _broadcast(game.id, game)

    def WatchGame(self, request, context):
        """
        Streams state to one watcher until it disconnects. The game's lock
        is only held for the brief register/unregister steps below — never
        for the streaming loop itself, since that runs for the connection's
        entire lifetime and must not block other clients' requests.
        """
        game_id, player_id = request.game_id, request.player_id
        q = self._register_watcher(game_id, player_id, context)
        try:
            yield from self._stream_from_queue(q, context)
        finally:
            self._unregister_watcher(game_id, player_id, q)

    def _register_watcher(self, game_id, player_id, context) -> queue.Queue:
        """Briefly locks the game to add a new watcher queue and get an initial snapshot."""
        game, lock = _get_game_and_lock(game_id, context)
        q = queue.Queue()
        with lock:
            _watchers[game_id].append(q)
            q.put(_to_proto_state(game))  # sync new watcher immediately
        return q

    @staticmethod
    def _stream_from_queue(q: queue.Queue, context):
        """Runs unlocked for the connection's duration — never touches game/registry state directly."""
        while context.is_active():
            try:
                yield q.get(timeout=1)
            except queue.Empty:
                continue

    def _unregister_watcher(self, game_id, player_id, q: queue.Queue) -> None:
        """
        Briefly locks the game to remove this watcher and treat their
        disconnect as leaving the game entirely (Option A): they come out
        of the game and the turn order so they no longer appear on anyone's
        board, and if it was their turn, play moves on to the next player.
        """
        with _registry_lock:
            game = _games.get(game_id)
            lock = _game_locks.get(game_id)
        if not game:
            return
        with lock:
            if q in _watchers.get(game_id, []):
                _watchers[game_id].remove(q)

            player = next((p for p in game.players if p.id == player_id), None)
            if player is None:
                return  # already left some other way

            # _remove_player advances play off the leaver when it is their
            # turn, and otherwise holds the index on the current player.
            # Calling pass_turn() first instead advanced the index and then
            # let the removal shift it again, landing a seat too far and
            # silently skipping the next player's turn.
            _remove_player(game, player)

            _broadcast(game_id, game)
            print(f"[server] {player.name} ({player_id}) disconnected and was removed from {game_id}")
        _discard_empty_game(game_id)

class GameServicer(pb_grpc.GameServicer):

    def GetState(self, request, context):
        game, lock = _get_game_and_lock(request.game_id, context)
        with lock:
            return _to_proto_state(game)

    def PlayTurn(self, request, context):
        game, lock = _get_game_and_lock(request.game_id, context)
        with lock:
            player = _find_player(game, request.player_id, context)
            _require_turn(game, player, context)

            if player.lose_next_turn:
                # Serving a skipped turn: no cards are played at all.
                # execute_turn clears the flag and advances play, and never
                # looks at the objective/action arguments, so don't index
                # into the hand with indices the client didn't mean.
                game.execute_turn(player, None, [])
                _broadcast(game.id, game)
                return pb.TurnResult(lose_turn=True, new_state=_to_proto_state(game))

            error = _validate_operation(
                player, request.objective_index, list(request.action_indices)
            )
            if error:
                context.abort(grpc.StatusCode.INVALID_ARGUMENT, error)

            obj = player.hand.objective_cards[request.objective_index]
            actions = [player.hand.non_objective_cards[i] for i in request.action_indices]
            try:
                result = game.execute_turn(player, obj, actions)
            except ValueError as e:
                context.abort(grpc.StatusCode.FAILED_PRECONDITION, str(e))
                return
            _broadcast(game.id, game)
            if result is None:
                if game.status == GameStats.FINISHED:
                    return pb.TurnResult(success=True, new_state=_to_proto_state(game))
                return pb.TurnResult(lose_turn=True, new_state=_to_proto_state(game))
            return pb.TurnResult(**result, new_state=_to_proto_state(game))

    def DiscardCard(self, request, context):
        game, lock = _get_game_and_lock(request.game_id, context)
        with lock:
            player = _find_player(game, request.player_id, context)
            _require_turn(game, player, context)
            try:
                card = player.hand.non_objective_cards[request.card_index]
            except IndexError:
                context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Invalid card index")
                return
            game.discard_card(player, card)
            return _broadcast(game.id, game)

    def DrawCards(self, request, context):
        game, lock = _get_game_and_lock(request.game_id, context)
        with lock:
            player = _find_player(game, request.player_id, context)
            _require_turn(game, player, context)
            try:
                events = game.draw_and_resolve_glitches(player, 2)
            except ValueError as e:
                context.abort(grpc.StatusCode.FAILED_PRECONDITION, str(e))
                return
            return pb.DrawResult(glitch_events=events, new_state=_broadcast(game.id, game))

    def ResolveDiscard(self, request, context):
        game, lock = _get_game_and_lock(request.game_id, context)
        with lock:
            # Deliberately no _require_turn here: a pending discard can be
            # left over from this player's own last turn and must stay
            # resolvable once play has moved on.
            player = _find_player(game, request.player_id, context)
            try:
                events = game.resolve_pending_discard(player, list(request.card_indices))
            except (ValueError, IndexError) as e:
                context.abort(grpc.StatusCode.FAILED_PRECONDITION, str(e))
                return
            return pb.DrawResult(glitch_events=events, new_state=_broadcast(game.id, game))

    def SkipTurn(self, request, context):
        game, lock = _get_game_and_lock(request.game_id, context)
        with lock:
            player = _find_player(game, request.player_id, context)
            _require_turn(game, player, context)
            game.pass_turn()
            return _broadcast(game.id, game)

    def LeaveGame(self, request, context):
        game, lock = _get_game_and_lock(request.game_id, context)
        with lock:
            player = _find_player(game, request.player_id, context)
            _remove_player(game, player)
            print(f"[server] {player.name} left {game.id}")
            state = _broadcast(game.id, game)
        _discard_empty_game(request.game_id)
        return state


# ── Entry point ───────────────────────────────────────────────────────────

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    pb_grpc.add_LobbyServicer_to_server(LobbyServicer(), server)
    pb_grpc.add_GameServicer_to_server(GameServicer(), server)
    server.add_insecure_port("[::]:50051")
    server.start()
    print("[server] Listening on port 50051")
    server.wait_for_termination()


if __name__ == "__main__":
    serve()