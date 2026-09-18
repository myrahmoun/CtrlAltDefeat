"""
Client widgets and the lobby flow.

The lobby tests drive real MainWindow instances against a real server
through actual button clicks, because the interesting behaviour lives in
the signal wiring between the widgets, the background workers and the
watch stream — none of which a unit test of the widget alone would reach.
"""

import pytest

from proto import basic_pb2 as pb
from client.view_model import game_state_from_proto
from client.widgets.hand_widget import HandWidget
from client.widgets.controls_widget import ControlsWidget
from client.widgets.lobby_widgets import LobbyWidget
from client.main_window import MainWindow


# ── View model ────────────────────────────────────────────────────────────

def test_state_translation_resolves_the_card_oneof(qapp, server, hosted_game):
    game_id, _ = hosted_game()
    view = game_state_from_proto(server.game.GetState(pb.StateRequest(game_id=game_id)))

    assert view.status == "playing"
    assert len(view.players) == 3
    for player in view.players:
        assert player.pending_discard is None
        for card in player.hand.non_objective_cards:
            # every card resolved to one concrete view type
            assert hasattr(card, "category") or hasattr(card, "glitch_type")


def test_pending_discard_survives_translation(qapp, server, hosted_game):
    game_id, _ = hosted_game()
    game = server.module._games[game_id]
    game.players[0].pending_discard = {
        "count": 2, "target_category": "Technology", "reason": "glitch",
    }

    view = game_state_from_proto(server.game.GetState(pb.StateRequest(game_id=game_id)))

    assert view.player(game.players[0].id).pending_discard == {
        "count": 2, "target_category": "Technology", "reason": "glitch",
    }


# ── Widgets in isolation ──────────────────────────────────────────────────

def test_controls_are_disabled_when_it_is_not_your_turn(qapp):
    controls = ControlsWidget()
    assert not controls._play_button.isEnabled()
    controls.set_my_turn(True)
    assert controls._play_button.isEnabled()


def test_hand_widget_requires_one_card_of_each_category(qapp, server, hosted_game):
    game_id, _ = hosted_game()
    view = game_state_from_proto(server.game.GetState(pb.StateRequest(game_id=game_id)))
    me = view.player(view.current_player_id)

    hand = HandWidget()
    hand.update_from(me.hand)
    hand.set_mode("play")

    assert not hand._confirm_button.isEnabled()
    hand._toggle_objective(0)
    assert not hand._confirm_button.isEnabled(), "an objective alone is not an operation"


def test_lobby_buttons_follow_the_fields(qapp):
    lobby = LobbyWidget()
    assert not lobby._create_button.isEnabled()
    assert not lobby._join_button.isEnabled()

    lobby._server_field.setText("localhost:50051")
    lobby._name_field.setText("Alice")
    assert lobby._create_button.isEnabled()
    assert not lobby._join_button.isEnabled(), "joining needs a game id"

    lobby._game_id_field.setText("abc123")
    assert not lobby._create_button.isEnabled(), "creating needs an empty game id"
    assert lobby._join_button.isEnabled()


def test_lobby_start_button_unlocks_at_three_players(qapp, server, lobby_game):
    game_id, _ = lobby_game("A", "B")
    lobby = LobbyWidget()

    def render():
        lobby.update_from(game_state_from_proto(
            server.game.GetState(pb.StateRequest(game_id=game_id))))

    render()
    assert lobby._player_list.count() == 2
    assert not lobby._start_button.isEnabled()
    assert "1 more" in lobby._count_label.text()

    server.lobby.JoinGame(pb.JoinRequest(game_id=game_id, player_name="C"))
    render()
    assert lobby._player_list.count() == 3
    assert lobby._start_button.isEnabled()
    assert "ready to start" in lobby._count_label.text()


def test_lobby_shows_the_game_id_for_sharing(qapp, server, lobby_game):
    game_id, _ = lobby_game("A")
    lobby = LobbyWidget()
    lobby.update_from(game_state_from_proto(
        server.game.GetState(pb.StateRequest(game_id=game_id))))
    assert game_id in lobby._game_id_label.text()


# ── The lobby end to end ──────────────────────────────────────────────────

@pytest.fixture
def windows(qapp):
    """Track MainWindows so they're always closed, even on failure."""
    opened = []
    yield opened
    for window in opened:
        window.close()


def open_window(windows, address, name, game_id=""):
    window = MainWindow()
    windows.append(window)
    window.show()
    lobby = window._lobby_widget
    lobby._server_field.setText(address)
    lobby._name_field.setText(name)
    lobby._game_id_field.setText(game_id)
    return window


def test_creating_joining_and_starting_a_game(qapp, pump, server, windows):
    host = open_window(windows, server.address, "Alice")
    assert host._stack.currentIndex() == MainWindow.LOBBY_PAGE

    host._lobby_widget._create_button.click()
    assert pump(lambda: host.game_id and host.player_id), "host never joined"
    game_id = host.game_id
    assert pump(lambda: host._lobby_widget._player_list.count() == 1)
    assert not host._lobby_widget._start_button.isEnabled()

    joiners = []
    for name in ("Bob", "Cara"):
        window = open_window(windows, server.address, name, game_id)
        window._lobby_widget._join_button.click()
        assert pump(lambda w=window: bool(w.player_id)), f"{name} never joined"
        joiners.append(window)

    assert pump(lambda: host._lobby_widget._player_list.count() == 3)
    assert [host._lobby_widget._player_list.item(i).text() for i in range(3)] == [
        "1. Alice", "2. Bob", "3. Cara",
    ]
    assert host._lobby_widget._start_button.isEnabled()

    host._lobby_widget._start_button.click()
    assert pump(lambda: host._stack.currentIndex() == MainWindow.GAME_PAGE)
    assert pump(lambda: all(w._stack.currentIndex() == MainWindow.GAME_PAGE
                            for w in joiners)), "joiners never left the lobby"

    everyone = [host] + joiners
    on_turn = [w for w in everyone if w._latest_state.current_player_id == w.player_id]
    assert len(on_turn) == 1
    assert on_turn[0]._controls_widget._play_button.isEnabled()
    for window in everyone:
        if window is not on_turn[0]:
            assert not window._controls_widget._play_button.isEnabled()


def test_a_failed_join_reports_on_the_lobby(qapp, pump, server, windows):
    host = open_window(windows, server.address, "Alice")
    host._lobby_widget._create_button.click()
    assert pump(lambda: bool(host.game_id))

    clash = open_window(windows, server.address, "Alice", host.game_id)
    clash._lobby_widget._join_button.click()

    assert pump(lambda: "already taken" in clash._lobby_widget._status_label.text())
    assert clash._stack.currentIndex() == MainWindow.LOBBY_PAGE
    assert clash._lobby_widget._join_button.isEnabled(), "controls stayed locked"


def test_joining_an_unknown_game_reports_on_the_lobby(qapp, pump, server, windows):
    window = open_window(windows, server.address, "Alice", "no-such-game")
    window._lobby_widget._join_button.click()

    assert pump(lambda: "not found" in window._lobby_widget._status_label.text().lower())
    assert window._stack.currentIndex() == MainWindow.LOBBY_PAGE


# ── Operation panel ───────────────────────────────────────────────────────

from client.widgets.operation_widget import OperationWidget, SLOT_CATEGORIES
from client.widgets.event_log_widget import EventLogWidget
from client.view_model import ActionCardView, ObjectiveCardView


def action(category, responsibility=0, effect=0):
    return ActionCardView(name=f"{category} card", description="d", category=category,
                          responsibility=responsibility, effect=effect)


def objective(responsibility=0, effect=0):
    return ObjectiveCardView(name="An objective", description="d",
                             responsibility=responsibility, effect=effect)


def full_operation(objective_r=0, objective_e=0, action_r=0, action_e=0):
    return objective(objective_r, objective_e), {
        c: action(c, action_r, action_e) for c in SLOT_CATEGORIES
    }


def test_operation_panel_starts_empty(qapp):
    panel = OperationWidget()
    assert "Responsibility 0" in panel._totals_label.text()
    assert "Still needed" in panel._verdict_label.text()


def test_operation_totals_include_the_objective(qapp):
    panel = OperationWidget()
    panel.update_from(*full_operation(objective_r=2, objective_e=6,
                                      action_r=1, action_e=1))
    assert "Responsibility 6" in panel._totals_label.text()
    assert "Effectiveness 10" in panel._totals_label.text()


def test_operation_panel_lists_what_is_missing(qapp):
    panel = OperationWidget()
    panel.update_from(objective(), {"Intelligence": action("Intelligence")})
    verdict = panel._verdict_label.text()
    assert "Technology" in verdict and "Governance" in verdict
    assert "Intelligence" not in verdict


def test_operation_panel_needs_an_objective_too(qapp):
    panel = OperationWidget()
    panel.update_from(None, {c: action(c) for c in SLOT_CATEGORIES})
    assert "an objective" in panel._verdict_label.text()


@pytest.mark.parametrize("responsibility, expected", [
    (4, "Succeeds automatically"),
    (2, "3 or higher"),
    (0, "Needs a 6"),
])
def test_operation_panel_explains_the_die_band(qapp, responsibility, expected):
    panel = OperationWidget()
    panel.update_from(*full_operation(objective_r=responsibility))
    assert expected in panel._verdict_label.text()


@pytest.mark.parametrize("responsibility, warned", [(0, True), (2, True), (3, False), (5, False)])
def test_operation_panel_warns_below_the_finishing_threshold(qapp, responsibility, warned):
    panel = OperationWidget()
    panel.update_from(*full_operation(objective_r=responsibility))
    assert ("finishing line" in panel._verdict_label.text()) is warned


def test_hand_widget_reports_its_selection(qapp, server, hosted_game):
    game_id, _ = hosted_game()
    game = server.module._games[game_id]
    from src.cards import ActionCard, CardCategory
    player = game.get_current_player()
    player.hand.non_objective_cards = [
        ActionCard("Intel", "d", CardCategory.INTELLIGENCE, responsibility=2, effect=1),
        ActionCard("Tech", "d", CardCategory.TECHNOLOGY, responsibility=1, effect=3),
    ]
    view = game_state_from_proto(server.game.GetState(pb.StateRequest(game_id=game_id)))
    me = view.player(player.id)

    hand = HandWidget()
    hand.update_from(me.hand)
    hand.set_mode("play")

    assert hand.current_selection() == (None, {})

    hand._toggle_objective(0)
    hand._toggle_action(0)
    chosen_objective, by_category = hand.current_selection()
    assert chosen_objective is me.hand.objective_cards[0]
    assert list(by_category) == ["Intelligence"]

    hand._toggle_action(1)
    assert sorted(hand.current_selection()[1]) == ["Intelligence", "Technology"]


def test_hand_widget_reports_nothing_in_discard_mode(qapp, server, hosted_game):
    game_id, _ = hosted_game()
    view = game_state_from_proto(server.game.GetState(pb.StateRequest(game_id=game_id)))
    hand = HandWidget()
    hand.update_from(view.player(view.current_player_id).hand)
    hand.set_mode("discard", count=1)
    hand._select_discard(0)
    assert hand.current_selection() == (None, {})


# ── Event log ─────────────────────────────────────────────────────────────

def test_event_log_keeps_order_and_is_bounded(qapp):
    log = EventLogWidget()
    for i in range(250):
        log.append(f"entry {i}")
    entries = log.entries()
    assert len(entries) == 200
    assert entries[-1] == "entry 249"
    assert entries[0] == "entry 50"


def test_log_records_moves_departures_and_the_winner(qapp, pump, server, windows):
    """
    Derived purely by diffing states, since the server pushes snapshots
    rather than events.
    """
    host = open_window(windows, server.address, "Alice")
    host._lobby_widget._create_button.click()
    assert pump(lambda: bool(host.game_id))
    joiners = []
    for name in ("Bob", "Cara"):
        window = open_window(windows, server.address, name, host.game_id)
        window._lobby_widget._join_button.click()
        assert pump(lambda w=window: bool(w.player_id))
        joiners.append(window)
    host._lobby_widget._start_button.click()
    assert pump(lambda: host._stack.currentIndex() == MainWindow.GAME_PAGE)

    assert "Game started." in host._event_log.entries()
    assert any("turn" in e for e in host._event_log.entries())

    # a move by another player shows up without that player telling us
    game = server.module._games[host.game_id]
    mover = next(p for p in game.players if p.id != host.player_id)
    mover.board_position = 4
    server.game.SkipTurn(pb.SkipRequest(
        game_id=host.game_id, player_id=game.get_current_player().id))
    assert pump(lambda: any("advanced 4 spaces" in e for e in host._event_log.entries()))

    # and so does a departure
    leaver = joiners[0]
    leaver_name = "Bob"
    server.game.LeaveGame(pb.LeaveRequest(
        game_id=host.game_id, player_id=leaver.player_id))
    assert pump(lambda: any(f"{leaver_name} left" in e for e in host._event_log.entries()))
