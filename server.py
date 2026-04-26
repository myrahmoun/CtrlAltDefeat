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

def _to_proto_action(card) -> game_pb2.ActionCard:
    return game_pb2.ActionCard(
        name=card.name,
        description=card.description,
        category=card.category,
        responsibility=card.responsibility,
        effect=card.effect,
    )


def _to_proto_objective(card) -> game_pb2.ObjectiveCard:
    return game_pb2.ObjectiveCard(
        name=card.name,
        description=card.description,
        responsibility=card.responsibility,
        effect=card.effect,
    )


def _to_proto_player(player) -> game_pb2.Player:
    return game_pb2.Player(
        id=player.id,
        name=player.name,
        board_position=player.boardPosition,
        lose_next_turn=player.lose_next_turn,
        hand=game_pb2.Hand(
            action_cards=[_to_proto_action(c) for c in player.hand.action_cards],
            objective_cards=[_to_proto_objective(c) for c in player.hand.objective_cards],
        ),
    )


def _to_proto_state(game: Game) -> game_pb2.GameState:
    current = game.get_current_player() if game.status == GameStats.PLAYING else None
    return game_pb2.GameState(
        game_id=game.id,
        status=game.status.name.lower(),
        players=[_to_proto_player(p) for p in game.players],
        current_player_id=current.id if current else "",
        winner_id=game.winner.id if game.winner else "",
    )


def _find_player(game: Game, player_id: str) -> GamePlayer:
    for p in game.players:
        if p.id == player_id:
            return p
    raise KeyError(f"Player {player_id} not found in game {game.id}")


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
        game = _games.get(request.game_id)
        if not game:
            context.abort(grpc.StatusCode.NOT_FOUND, f"Game {request.game_id} not found")

        if any(p.name == request.player_name for p in game.players):
            context.abort(grpc.StatusCode.ALREADY_EXISTS, f"Name '{request.player_name}' is already taken")

        player = GamePlayer(request.player_name)
        game.players.append(player)
        print(f"[server] {player.name} ({player.id}) joined game {game.id}")
        _broadcast(game.id, game)
        return game_pb2.JoinResponse(player_id=player.id, state=_to_proto_state(game))

    def StartGame(self, request, context):
        game = _games.get(request.game_id)
        if not game:
            context.abort(grpc.StatusCode.NOT_FOUND, f"Game {request.game_id} not found")

        if game.status != GameStats.LOBBY:
            return _to_proto_state(game)

        game.setup_game()
        print(f"[server] Game {game.id} started")
        _broadcast(game.id, game)
        return _to_proto_state(game)

    def GetState(self, request, context):
        game = _games.get(request.game_id)
        if not game:
            context.abort(grpc.StatusCode.NOT_FOUND, f"Game {request.game_id} not found")
        return _to_proto_state(game)

    def PlayTurn(self, request, context):
        game = _games.get(request.game_id)
        if not game:
            context.abort(grpc.StatusCode.NOT_FOUND, f"Game {request.game_id} not found")

        player = _find_player(game, request.player_id)
        current = game.get_current_player()
        if player.id != current.id:
            context.abort(grpc.StatusCode.FAILED_PRECONDITION, "It is not your turn")

        # Draw 2 action cards at the start of the turn
        for _ in range(2):
            game._refill_if_empty(game.action_pile)
            card = game.action_pile.draw()
            if card and len(player.hand.action_cards) < 6:
                player.hand.action_cards.append(card)

        obj = player.hand.objective_cards[request.objective_index]
        actions = [player.hand.action_cards[i] for i in request.action_indices]

        result = game.execute_turn(player, obj, actions)
        _broadcast(game.id, game)

        if result is None:
            # lose_next_turn path — execute_turn returns None after skipping
            return game_pb2.TurnResult(lose_turn=True, new_state=_to_proto_state(game))

        return game_pb2.TurnResult(
            success=result['success'],
            spaces_moved=result['spaces_moved'],
            bonus=result['bonus'],
            lose_turn=result['lose_turn'],
            responsibility=result['responsibility'],
            effect=result['effect'],
            new_state=_to_proto_state(game),
        )

    def DiscardCard(self, request, context):
        game = _games.get(request.game_id)
        if not game:
            context.abort(grpc.StatusCode.NOT_FOUND, f"Game {request.game_id} not found")

        player = _find_player(game, request.player_id)
        try:
            card = player.hand.action_cards[request.card_index]
            player.hand.action_cards.remove(card)
            game.discard_pile.add(card)
        except IndexError:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Invalid card index")

        _broadcast(game.id, game)
        return _to_proto_state(game)

    def SkipTurn(self, request, context):
        game = _games.get(request.game_id)
        if not game:
            context.abort(grpc.StatusCode.NOT_FOUND, f"Game {request.game_id} not found")

        player = _find_player(game, request.player_id)
        for _ in range(2):
            game._refill_if_empty(game.action_pile)
            card = game.action_pile.draw()
            if card and len(player.hand.action_cards) < 6:
                player.hand.action_cards.append(card)

        game.pass_turn()
        _broadcast(game.id, game)
        return _to_proto_state(game)

    def LeaveGame(self, request, context):
        game = _games.get(request.game_id)
        if not game:
            context.abort(grpc.StatusCode.NOT_FOUND, f"Game {request.game_id} not found")

        player = _find_player(game, request.player_id)
        game.players.remove(player)
        if player in game.turn_order:
            game.turn_order.remove(player)
        print(f"[server] {player.name} left game {game.id}")
        _broadcast(game.id, game)
        return _to_proto_state(game)

    def WatchGame(self, request, context):
        game = _games.get(request.game_id)
        if not game:
            context.abort(grpc.StatusCode.NOT_FOUND, f"Game {request.game_id} not found")

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