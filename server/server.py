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


def _find_player(game: Game, player_id: str) -> GamePlayer:
    for p in game.players:
        if p.id == player_id:
            return p
    raise KeyError(f"Player {player_id} not found in game {game.id}")


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
    current = game.get_current_player() if game.status == GameStats.PLAYING else None
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
            **({"pending_glitch_discard": p.pending_glitch_discard} if p.pending_glitch_discard else {}),
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
            game.setup_game()
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
        disconnect as leaving the game entirely (Option A): if it was their
        turn, advance play first, then remove them from the game and turn
        order so they no longer appear on anyone's board.
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

            was_current = (
                game.status == GameStats.PLAYING
                and game.get_current_player().id == player_id
            )
            if was_current:
                game.pass_turn()

            game.players.remove(player)
            if player in game.turn_order:
                game.turn_order.remove(player)

            _broadcast(game_id, game)
            print(f"[server] {player.name} ({player_id}) disconnected and was removed from {game_id}")

class GameServicer(pb_grpc.GameServicer):

    def GetState(self, request, context):
        game, lock = _get_game_and_lock(request.game_id, context)
        with lock:
            return _to_proto_state(game)

    def PlayTurn(self, request, context):
        game, lock = _get_game_and_lock(request.game_id, context)
        with lock:
            player = _find_player(game, request.player_id)
            if player.id != game.get_current_player().id:
                context.abort(grpc.StatusCode.FAILED_PRECONDITION, "It is not your turn")
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
            player = _find_player(game, request.player_id)
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
            player = _find_player(game, request.player_id)
            try:
                events = game.draw_and_resolve_glitches(player, 2)
            except ValueError as e:
                context.abort(grpc.StatusCode.FAILED_PRECONDITION, str(e))
                return
            return pb.DrawResult(glitch_events=events, new_state=_broadcast(game.id, game))

    def ResolveGlitchDiscard(self, request, context):
        game, lock = _get_game_and_lock(request.game_id, context)
        with lock:
            player = _find_player(game, request.player_id)
            try:
                events = game.resolve_pending_glitch_discard(player, list(request.card_indices))
            except (ValueError, IndexError) as e:
                context.abort(grpc.StatusCode.FAILED_PRECONDITION, str(e))
                return
            return pb.DrawResult(glitch_events=events, new_state=_broadcast(game.id, game))

    def SkipTurn(self, request, context):
        game, lock = _get_game_and_lock(request.game_id, context)
        with lock:
            game.pass_turn()
            return _broadcast(game.id, game)

    def LeaveGame(self, request, context):
        game, lock = _get_game_and_lock(request.game_id, context)
        with lock:
            player = _find_player(game, request.player_id)
            game.players.remove(player)
            if player in game.turn_order:
                game.turn_order.remove(player)
            print(f"[server] {player.name} left {game.id}")
            return _broadcast(game.id, game)


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