import grpc
import uuid
import queue
import threading
from concurrent import futures

from game import Game, GameStats
from player import Player as GamePlayer
import basic_pb2 as pb
import basic_pb2_grpc as pb_grpc


# Active games and their watcher queues
_games: dict[str, Game] = {}
_watchers: dict[str, list[queue.Queue]] = {}
_lock = threading.Lock()


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
            board_position=p.boardPosition,
            lose_next_turn=p.lose_next_turn,
            hand=pb.Hand(
                action_cards=[pb.ActionCard(
                    name=c.name, description=c.description, category=c.category,
                    responsibility=c.responsibility, effect=c.effect,
                ) for c in p.hand.action_cards],
                objective_cards=[pb.ObjectiveCard(
                    name=c.name, description=c.description,
                    responsibility=c.responsibility, effect=c.effect,
                ) for c in p.hand.objective_cards],
            ),
        ) for p in game.players],
    )


def _broadcast(game_id: str, game: Game) -> pb.GameState:
    state = _to_proto_state(game)
    for q in _watchers.get(game_id, []):
        q.put(state)
    return state


# ── Servicers ─────────────────────────────────────────────────────────────

class LobbyServicer(pb_grpc.LobbyServicer):

    def CreateGame(self, request, context):
        with _lock:
            game_id = str(uuid.uuid4())[:8]
            _games[game_id] = Game(game_id)
            _watchers[game_id] = []
            print(f"[server] Game created: {game_id}")
            return _to_proto_state(_games[game_id])

    def JoinGame(self, request, context):
        with _lock:
            game = _get_game(request.game_id, context)
            if any(p.name == request.player_name for p in game.players):
                context.abort(grpc.StatusCode.ALREADY_EXISTS, f"Name '{request.player_name}' is already taken")
            player = GamePlayer(request.player_name)
            game.players.append(player)
            print(f"[server] {player.name} joined {game.id}")
            return pb.JoinResponse(player_id=player.id, state=_broadcast(game.id, game))

    def StartGame(self, request, context):
        with _lock:
            game = _get_game(request.game_id, context)
            if game.status != GameStats.LOBBY:
                return _to_proto_state(game)
            game.setup_game()
            print(f"[server] Game {game.id} started")
            return _broadcast(game.id, game)

    def WatchGame(self, request, context):
        with _lock:
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
            with _lock:
                _watchers[request.game_id].remove(q)
                game = _games.get(request.game_id)
                if (game and game.status == GameStats.PLAYING
                        and game.get_current_player().id == request.player_id):
                    game.pass_turn()
                    _broadcast(request.game_id, game)
                    print(f"[server] {request.player_id} disconnected — turn auto-skipped")


class GameServicer(pb_grpc.GameServicer):

    def GetState(self, request, context):
        with _lock:
            return _to_proto_state(_get_game(request.game_id, context))

    def PlayTurn(self, request, context):
        with _lock:
            game = _get_game(request.game_id, context)
            player = _find_player(game, request.player_id)
            if player.id != game.get_current_player().id:
                context.abort(grpc.StatusCode.FAILED_PRECONDITION, "It is not your turn")
            obj = player.hand.objective_cards[request.objective_index]
            actions = [player.hand.action_cards[i] for i in request.action_indices]
            result = game.execute_turn(player, obj, actions)
            _broadcast(game.id, game)
            if result is None:
                if game.status == GameStats.FINISHED:
                    return pb.TurnResult(success=True, new_state=_to_proto_state(game))
                return pb.TurnResult(lose_turn=True, new_state=_to_proto_state(game))
            return pb.TurnResult(**result, new_state=_to_proto_state(game))

    def DiscardCard(self, request, context):
        with _lock:
            game = _get_game(request.game_id, context)
            player = _find_player(game, request.player_id)
            try:
                card = player.hand.action_cards[request.card_index]
                player.hand.action_cards.remove(card)
                game.discard_pile.add(card)
            except IndexError:
                context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Invalid card index")
            return _broadcast(game.id, game)

    def DrawCards(self, request, context):
        with _lock:
            game = _get_game(request.game_id, context)
            player = _find_player(game, request.player_id)
            for _ in range(2):
                game._refill_if_empty(game.action_pile)
                card = game.action_pile.draw()
                if card:
                    player.hand.action_cards.append(card)
            return _broadcast(game.id, game)

    def SkipTurn(self, request, context):
        with _lock:
            game = _get_game(request.game_id, context)
            game.pass_turn()
            return _broadcast(game.id, game)

    def LeaveGame(self, request, context):
        with _lock:
            game = _get_game(request.game_id, context)
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
