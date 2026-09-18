"""
The gRPC layer: turn ownership, request validation, and what happens to a
game when players leave or drop their connection.

These run against a real server over a real channel rather than calling the
servicers directly, so the status codes clients actually see are covered.
"""

import grpc
import pytest

from proto import basic_pb2 as pb
from src.cards import ActionCard, CardCategory as Category

REQUIRED = (Category.INTELLIGENCE, Category.TECHNOLOGY,
            Category.GOVERNANCE, Category.CYBERSECURITY)


def code_of(excinfo):
    return excinfo.value.code()


def full_hand(player):
    """Give a player exactly one action card of each category."""
    player.hand.non_objective_cards = [
        ActionCard(f"{c} card", "d", c, responsibility=1, effect=1) for c in REQUIRED
    ]


# ── Lobby ─────────────────────────────────────────────────────────────────

def test_create_and_join(server):
    game_id = server.lobby.CreateGame(pb.CreateGameRequest()).game_id
    response = server.lobby.JoinGame(
        pb.JoinRequest(game_id=game_id, player_name="Alice"))
    assert response.player_id
    assert [p.name for p in response.state.players] == ["Alice"]


def test_duplicate_names_are_rejected(server):
    game_id = server.lobby.CreateGame(pb.CreateGameRequest()).game_id
    server.lobby.JoinGame(pb.JoinRequest(game_id=game_id, player_name="Alice"))
    with pytest.raises(grpc.RpcError) as excinfo:
        server.lobby.JoinGame(pb.JoinRequest(game_id=game_id, player_name="Alice"))
    assert code_of(excinfo) is grpc.StatusCode.ALREADY_EXISTS


def test_unknown_game_is_not_found(server):
    with pytest.raises(grpc.RpcError) as excinfo:
        server.game.GetState(pb.StateRequest(game_id="nope"))
    assert code_of(excinfo) is grpc.StatusCode.NOT_FOUND


def test_unknown_player_is_not_found(server, hosted_game):
    game_id, _ = hosted_game()
    with pytest.raises(grpc.RpcError) as excinfo:
        server.game.DrawCards(pb.DrawRequest(game_id=game_id, player_id="nobody"))
    assert code_of(excinfo) is grpc.StatusCode.NOT_FOUND


def test_starting_a_started_game_is_a_no_op(server, hosted_game):
    game_id, _ = hosted_game()
    state = server.lobby.StartGame(pb.StartRequest(game_id=game_id))
    assert state.status == "playing"


# ── Turn ownership ────────────────────────────────────────────────────────

@pytest.mark.parametrize("call", ["PlayTurn", "DrawCards", "DiscardCard", "SkipTurn"])
def test_actions_require_it_to_be_your_turn(server, hosted_game, call):
    game_id, ids = hosted_game()
    current = server.game.GetState(pb.StateRequest(game_id=game_id)).current_player_id
    other = next(pid for pid in ids.values() if pid != current)

    requests = {
        "PlayTurn": pb.TurnRequest(game_id=game_id, player_id=other,
                                   objective_index=0, action_indices=[0, 1, 2, 3]),
        "DrawCards": pb.DrawRequest(game_id=game_id, player_id=other),
        "DiscardCard": pb.DiscardRequest(game_id=game_id, player_id=other, card_index=0),
        "SkipTurn": pb.SkipRequest(game_id=game_id, player_id=other),
    }
    with pytest.raises(grpc.RpcError) as excinfo:
        getattr(server.game, call)(requests[call])
    assert code_of(excinfo) is grpc.StatusCode.FAILED_PRECONDITION


def test_skip_turn_by_a_bystander_does_not_advance_play(server, hosted_game):
    game_id, ids = hosted_game()
    before = server.game.GetState(pb.StateRequest(game_id=game_id)).current_player_id
    other = next(pid for pid in ids.values() if pid != before)

    with pytest.raises(grpc.RpcError):
        server.game.SkipTurn(pb.SkipRequest(game_id=game_id, player_id=other))

    after = server.game.GetState(pb.StateRequest(game_id=game_id)).current_player_id
    assert after == before


def test_a_pending_discard_is_resolvable_out_of_turn(server, hosted_game):
    """
    Deliberately exempt from the turn check: a discard can be owed from the
    player's own previous turn and must stay resolvable once play moves on.
    """
    game_id, _ = hosted_game()
    game = server.module._games[game_id]
    waiting = game.turn_order[1]  # not the current player
    waiting.pending_discard = {"count": 1, "target_category": "", "reason": "hand_limit"}

    result = server.game.ResolveDiscard(pb.ResolveDiscardRequest(
        game_id=game_id, player_id=waiting.id, card_indices=[0]))

    assert result.new_state.game_id == game_id
    assert waiting.pending_discard is None


# ── Operation validation ──────────────────────────────────────────────────

def test_a_malformed_operation_is_rejected_without_costing_cards(server, hosted_game):
    """
    _execute_operation discards before evaluating, so an invalid operation
    used to destroy the hand and leak an UNKNOWN error.
    """
    game_id, _ = hosted_game()
    game = server.module._games[game_id]
    player = game.get_current_player()
    player.hand.non_objective_cards = [
        ActionCard(f"t{i}", "d", Category.TECHNOLOGY) for i in range(4)
    ]

    with pytest.raises(grpc.RpcError) as excinfo:
        server.game.PlayTurn(pb.TurnRequest(
            game_id=game_id, player_id=player.id,
            objective_index=0, action_indices=[0, 1, 2, 3]))

    assert code_of(excinfo) is grpc.StatusCode.INVALID_ARGUMENT
    assert len(player.hand.non_objective_cards) == 4
    assert game.get_current_player() is player


@pytest.mark.parametrize("objective_index, action_indices", [
    (0, [0, 0, 1, 2]),      # duplicate card
    (0, [0, 1, 2]),         # too few
    (0, [0, 1, 2, 3, 3]),   # too many
    (99, [0, 1, 2, 3]),     # objective out of range
    (0, [0, 1, 2, 99]),     # action out of range
])
def test_bad_operation_arguments_are_rejected(server, hosted_game,
                                              objective_index, action_indices):
    game_id, _ = hosted_game()
    game = server.module._games[game_id]
    player = game.get_current_player()
    full_hand(player)

    with pytest.raises(grpc.RpcError) as excinfo:
        server.game.PlayTurn(pb.TurnRequest(
            game_id=game_id, player_id=player.id,
            objective_index=objective_index, action_indices=action_indices))
    assert code_of(excinfo) is grpc.StatusCode.INVALID_ARGUMENT


def test_a_valid_operation_is_played_and_advances_the_turn(server, hosted_game):
    game_id, _ = hosted_game()
    game = server.module._games[game_id]
    player = game.get_current_player()
    full_hand(player)

    result = server.game.PlayTurn(pb.TurnRequest(
        game_id=game_id, player_id=player.id,
        objective_index=0, action_indices=[0, 1, 2, 3]))

    assert result.new_state.game_id == game_id
    assert game.get_current_player() is not player


# ── Leaving and disconnecting ─────────────────────────────────────────────

def test_the_last_player_in_turn_order_can_leave(server, hosted_game):
    """
    Removing them used to leave current_turn_index past the end of the list,
    which made every later GetState raise and bricked the game for everyone.
    """
    game_id, _ = hosted_game()
    game = server.module._games[game_id]
    game.current_turn_index = len(game.turn_order) - 1
    leaver = game.turn_order[-1]
    expected_next = game.turn_order[0]

    server.game.LeaveGame(pb.LeaveRequest(game_id=game_id, player_id=leaver.id))

    state = server.game.GetState(pb.StateRequest(game_id=game_id))
    assert leaver.name not in [p.name for p in state.players]
    assert state.current_player_id == expected_next.id


def test_leaving_mid_list_keeps_the_turn_on_the_current_player(server, hosted_game):
    game_id, _ = hosted_game("A", "B", "C", "D")
    game = server.module._games[game_id]
    game.current_turn_index = 2
    current = game.turn_order[2]
    leaver = game.turn_order[0]

    server.game.LeaveGame(pb.LeaveRequest(game_id=game_id, player_id=leaver.id))

    assert game.get_current_player() is current


def test_disconnecting_on_your_own_turn_passes_to_the_next_player(server, hosted_game):
    """
    pass_turn()-then-remove shifted the index twice and skipped a player.
    """
    game_id, _ = hosted_game("A", "B", "C", "D")
    game = server.module._games[game_id]
    game.current_turn_index = 0
    leaver, expected = game.turn_order[0], game.turn_order[1]

    server.module.LobbyServicer()._unregister_watcher(game_id, leaver.id, object())

    assert game.get_current_player() is expected


def test_disconnecting_out_of_turn_leaves_the_turn_alone(server, hosted_game):
    game_id, _ = hosted_game("A", "B", "C", "D")
    game = server.module._games[game_id]
    current = game.get_current_player()
    other = next(p for p in game.turn_order if p is not current)

    server.module.LobbyServicer()._unregister_watcher(game_id, other.id, object())

    assert game.get_current_player() is current


def test_an_emptied_game_is_dropped_from_the_registry(server, hosted_game):
    game_id, ids = hosted_game()
    for player_id in ids.values():
        server.game.LeaveGame(pb.LeaveRequest(game_id=game_id, player_id=player_id))
    assert game_id not in server.module._games


# ── End to end ────────────────────────────────────────────────────────────

def test_games_play_to_a_winner_over_grpc(server):
    """
    A scripted bot plays whole games through the real RPC surface — the
    broadest check that the rules, the server, and the protos agree.
    """
    categories = [c.value for c in REQUIRED]
    completed = 0

    for _ in range(5):
        game_id = server.lobby.CreateGame(pb.CreateGameRequest()).game_id
        ids = [server.lobby.JoinGame(
            pb.JoinRequest(game_id=game_id, player_name=n)).player_id
            for n in ("A", "B", "C")]
        server.lobby.StartGame(pb.StartRequest(game_id=game_id))

        for _ in range(600):
            state = server.game.GetState(pb.StateRequest(game_id=game_id))
            if state.winner_id:
                completed += 1
                break
            me = next(p for p in state.players if p.id == state.current_player_id)

            if me.HasField("pending_discard"):
                pending = me.pending_discard
                indices = [
                    i for i, c in enumerate(me.hand.non_objective_cards)
                    if not pending.target_category
                    or (c.WhichOneof("card") == "action"
                        and c.action.category == pending.target_category)
                ][:pending.count]
                server.game.ResolveDiscard(pb.ResolveDiscardRequest(
                    game_id=game_id, player_id=me.id, card_indices=indices))
                continue

            if me.lose_next_turn:
                server.game.PlayTurn(pb.TurnRequest(
                    game_id=game_id, player_id=me.id,
                    objective_index=0, action_indices=[]))
                continue

            chosen = {}
            for i, card in enumerate(me.hand.non_objective_cards):
                if card.WhichOneof("card") != "action":
                    continue
                category = card.action.category
                if category in categories and category not in chosen:
                    chosen[category] = i

            if len(chosen) == 4:
                server.game.PlayTurn(pb.TurnRequest(
                    game_id=game_id, player_id=me.id, objective_index=0,
                    action_indices=sorted(chosen.values())))
            else:
                server.game.DrawCards(pb.DrawRequest(game_id=game_id, player_id=me.id))

    assert completed == 5


def test_starting_with_too_few_players_is_a_precondition_failure(server, lobby_game):
    game_id, _ = lobby_game("A", "B")
    with pytest.raises(grpc.RpcError) as excinfo:
        server.lobby.StartGame(pb.StartRequest(game_id=game_id))
    assert code_of(excinfo) is grpc.StatusCode.FAILED_PRECONDITION
    assert "3-6 players" in excinfo.value.details()
