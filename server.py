import grpc
import uuid
import queue
from concurrent import futures

from game import Game, GameStats
from player import Player as GamePlayer
import game_pb2
import game_pb2_grpc


# Active games and their watcher queues
_games: dict[str, Game] = {}
_watchers: dict[str, list[queue.Queue]] = {}


# ── Helpers ───────────────────────────────────────────────────────────────

def _get_game(game_id, context):
    """Look up a game by ID, aborting with NOT_FOUND if missing."""
    game = _games.get(game_id)
    if not game:
        context.abort(grpc.StatusCode.NOT_FOUND, f"Game {game_id} not found")
    return game


def _find_player(game: Game, player_id: str) -> GamePlayer:
    for p in game.players:
        if p.id == player_id:
            return p
    raise KeyError(f"Player {player_id} not found in game {game.id}")


def _to_proto_state(game: Game) -> game_pb2.GameState:
    """Convert internal Game object to proto GameState."""
    current = game.get_current_player() if game.status == GameStats.PLAYING else None
    return game_pb2.GameState(
        game_id=game.id,
        status=game.status.name.lower(),
        current_player_id=current.id if current else "",
        winner_id=game.winner.id if game.winner else "",
        players=[game_pb2.Player(
            id=p.id,
            name=p.name,
            board_position=p.boardPosition,
            lose_next_turn=p.lose_next_turn,
            hand=game_pb2.Hand(
                action_cards=[game_pb2.ActionCard(
                    name=c.name, description=c.description, category=c.category,
                    responsibility=c.responsibility, effect=c.effect,
                ) for c in p.hand.action_cards],
                objective_cards=[game_pb2.ObjectiveCard(
                    name=c.name, description=c.description,
                    responsibility=c.responsibility, effect=c.effect,
                ) for c in p.hand.objective_cards],
            ),
        ) for p in game.players],
    )


def _broadcast(game_id: str, game: Game) -> None:
    state = _to_proto_state(game)
    for q in _watchers.get(game_id, []):
        q.put(state)


# ── Servicer ──────────────────────────────────────────────────────────────

class BeanBagServicer(game_pb2_grpc.BeanBagServicer):

    def CreateGame(self, request, context):
        game_id = str(uuid.uuid4())[:8]
        _games[game_id] = Game(game_id)
        _watchers[game_id] = []
        print(f"[server] Game created: {game_id}")
        return _to_proto_state(_games[game_id])

    def JoinGame(self, request, context):
        game = _get_game(request.game_id, context)
        if any(p.name == request.player_name for p in game.players):
            context.abort(grpc.StatusCode.ALREADY_EXISTS, f"Name '{request.player_name}' is already taken")
        player = GamePlayer(request.player_name)
        game.players.append(player)
        print(f"[server] {player.name} joined {game.id}")
        _broadcast(game.id, game)
        return game_pb2.JoinResponse(player_id=player.id, state=_to_proto_state(game))

    def StartGame(self, request, context):
        game = _get_game(request.game_id, context)
        if game.status != GameStats.LOBBY:
            return _to_proto_state(game)
        game.setup_game()
        print(f"[server] Game {game.id} started")
        _broadcast(game.id, game)
        return _to_proto_state(game)

    def GetState(self, request, context):
        return _to_proto_state(_get_game(request.game_id, context))

    def PlayTurn(self, request, context):
        game = _get_game(request.game_id, context)
        player = _find_player(game, request.player_id)
        if player.id != game.get_current_player().id:
            context.abort(grpc.StatusCode.FAILED_PRECONDITION, "It is not your turn")
        obj = player.hand.objective_cards[request.objective_index]
        actions = [player.hand.action_cards[i] for i in request.action_indices]
        result = game.execute_turn(player, obj, actions)
        _broadcast(game.id, game)
        if result is None:
            # lose_next_turn path — execute_turn returns None after skipping
            return game_pb2.TurnResult(lose_turn=True, new_state=_to_proto_state(game))
        return game_pb2.TurnResult(**result, new_state=_to_proto_state(game))

    def DiscardCard(self, request, context):
        game = _get_game(request.game_id, context)
        player = _find_player(game, request.player_id)
        try:
            card = player.hand.action_cards[request.card_index]
            player.hand.action_cards.remove(card)
            game.discard_pile.add(card)
        except IndexError:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Invalid card index")
        _broadcast(game.id, game)
        return _to_proto_state(game)

    def DrawCards(self, request, context):
        game = _get_game(request.game_id, context)
        player = _find_player(game, request.player_id)
        for _ in range(2):
            game._refill_if_empty(game.action_pile)
            card = game.action_pile.draw()
            if card:
                player.hand.action_cards.append(card)
        _broadcast(game.id, game)
        return _to_proto_state(game)

    def SkipTurn(self, request, context):
        game = _get_game(request.game_id, context)
        game.pass_turn()
        _broadcast(game.id, game)
        return _to_proto_state(game)

    def LeaveGame(self, request, context):
        game = _get_game(request.game_id, context)
        player = _find_player(game, request.player_id)
        game.players.remove(player)
        if player in game.turn_order:
            game.turn_order.remove(player)
        print(f"[server] {player.name} left {game.id}")
        _broadcast(game.id, game)
        return _to_proto_state(game)

    def WatchGame(self, request, context):
        game = _get_game(request.game_id, context)

        q = queue.Queue()
        _watchers[request.game_id].append(q)
        # Send current state immediately so the client is in sync on connect
        q.put(_to_proto_state(game))
        try:
            while context.is_active():
                try:
                    state = q.get(timeout=1)
                    yield state
                except queue.Empty:
                    continue
        finally:
            _watchers[request.game_id].remove(q)


# ── Entry point ───────────────────────────────────────────────────────────

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    game_pb2_grpc.add_BeanBagServicer_to_server(BeanBagServicer(), server)
    server.add_insecure_port("[::]:50051")
    server.start()
    print("[server] Listening on port 50051")
    server.wait_for_termination()


if __name__ == "__main__":
    serve()