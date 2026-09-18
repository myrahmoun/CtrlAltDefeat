"""
main_window.py

The visible application window and the only place code runs on the main
thread's Qt event loop (aside from app.py's startup lines).

Owns a GameActionWorker (created on the first connect, once the lobby has
supplied a server address) and, once a game is joined, a GameStreamWorker
(created only after game_id/player_id are known). Each worker is moved to
its own QThread here; MainWindow only ever talks to them via signals, never
by calling their methods directly.

Holds a QStackedWidget with two pages — the lobby, and the game itself
(board, hand, controls) — and swaps between them as the server's reported
status changes. It is the only place that translates widget clicks into
request_* calls, and the only place that translates incoming
GameState/TurnResult protos (via view_model) back into widget updates.
"""

import grpc
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QLabel, QMessageBox, QStackedWidget,
)

from client.network_worker import GameStreamWorker, GameActionWorker
from client.view_model import game_state_from_proto
from client.widgets.board_widget import BoardWidget
from client.widgets.hand_widget import HandWidget
from client.widgets.controls_widget import ControlsWidget
from client.widgets.lobby_widgets import LobbyWidget
from client.widgets.operation_widget import OperationWidget
from client.widgets.event_log_widget import EventLogWidget


def _glitch_log_line(event) -> str:
    """One-line summary of a resolved Glitch Card, for the game log."""
    if event.effect_type == "draw":
        return f"{event.name}: drew {event.count} extra card(s)."
    if event.effect_type == "skip_operation":
        return f"{event.name}: no operation this turn."
    if event.effect_type == "discard":
        category = f" {event.target_category}" if event.target_category else ""
        return f"{event.name}: discard {event.count}{category} card(s)."
    return f"{event.name}."


def _glitch_event_text(event) -> str:
    """Build the popup body for one resolved pb.GlitchEvent."""
    header = f"Glitch Card: {event.name}"
    if event.description:
        header += f"\n{event.description}"

    if event.effect_type == "draw":
        names = ", ".join(event.drawn_card_names) if event.drawn_card_names else "nothing (pile empty)"
        return f"{header}\n\nYou drew {event.count} more card(s): {names}"
    if event.effect_type == "skip_operation":
        return f"{header}\n\nYou can't play an operation this turn."
    if event.effect_type == "discard":
        category_note = f" {event.target_category}" if event.target_category else ""
        return f"{header}\n\nYou must discard{category_note} card(s) — choose which in your hand."
    return header


class MainWindow(QMainWindow):
    LOBBY_PAGE = 0
    GAME_PAGE = 1

    # --- UI -> action worker signals ---
    # Emitting these (never calling the worker's methods directly) is what
    # actually crosses onto the worker's thread safely — see the connect()
    # calls in _setup_action_worker, which route each of these to the
    # matching @Slot on GameActionWorker.
    _create_game_requested = Signal()
    _join_game_requested = Signal(dict)
    _start_game_requested = Signal()
    _play_turn_requested = Signal(dict)
    _discard_requested = Signal(dict)
    _draw_requested = Signal()
    _skip_requested = Signal()
    _leave_requested = Signal()
    _resolve_discard_requested = Signal(list)

    def __init__(self):
        super().__init__()
        # Filled in by _ensure_connected() once the player supplies a
        # server address on the lobby screen — there is nothing to connect
        # to before that, so no channel or worker exists yet.
        self.server_address: str | None = None
        self._channel = None
        self._action_thread: QThread | None = None
        self._action_worker: GameActionWorker | None = None

        # Local copies, kept in sync via the joined/game_created signals.
        self.game_id: str | None = None
        self.player_id: str | None = None

        # Created later, once we've joined a game — see _start_watching().
        self._stream_thread: QThread | None = None
        self._stream_worker: GameStreamWorker | None = None

        # Latest translated state, kept so widgets can be re-rendered
        # (e.g. switching HandWidget mode) without waiting for a new push.
        self._latest_state = None

        self._pending_player_name: str | None = None

        # Tracks whether the hand widget is currently forced into the
        # discard picker (a Glitch Card or the hand limit), so
        # on_state_updated only calls set_mode on the transition edges
        # (entering/leaving pending) rather than every broadcast, which
        # would otherwise wipe an in-progress selection.
        self._awaiting_forced_discard = False

        self._setup_ui()

    def _setup_ui(self) -> None:
        # Page 0 is the lobby, page 1 the game. on_state_updated swaps to
        # the game page once the server reports status "playing".
        self._stack = QStackedWidget()
        self._lobby_widget = LobbyWidget()
        self._stack.addWidget(self._lobby_widget)
        self._stack.addWidget(self._build_game_page())

        self.setCentralWidget(self._stack)
        self.resize(800, 900)
        self.setMinimumSize(400, 400)

        # Widget -> MainWindow (never widget -> worker directly)
        self._lobby_widget.create_clicked.connect(self._on_create_clicked)
        self._lobby_widget.join_clicked.connect(self._on_join_clicked)
        self._lobby_widget.start_clicked.connect(self.request_start_game)
        self._controls_widget.play_clicked.connect(self._on_play_clicked)
        self._controls_widget.draw_clicked.connect(self.request_draw)
        self._controls_widget.discard_clicked.connect(self._on_discard_clicked)
        self._controls_widget.skip_clicked.connect(self.request_skip)
        self._hand_widget.play_selection_ready.connect(self._on_play_selection_ready)
        self._hand_widget.discard_selection_ready.connect(self._on_discard_selection_ready)
        self._hand_widget.forced_discard_ready.connect(self._on_forced_discard_ready)
        self._hand_widget.selection_changed.connect(self._on_selection_changed)

    def _build_game_page(self) -> QWidget:
        """
        Top to bottom: who you are, what just happened, the board, the
        operation you're assembling, your hand, the turn actions, and the
        log. Only the log is given stretch, so everything above keeps its
        natural height and the leftover space goes somewhere useful
        instead of pooling as gaps between widgets.
        """
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(8)

        self._status_label = QLabel("Not connected.")
        self._status_label.setStyleSheet("font-size: 14px; font-weight: 600;")
        layout.addWidget(self._status_label)

        # Separate from _status_label (which on_state_updated rewrites on
        # every broadcast, including the one that always follows a turn):
        # without its own label, a turn's outcome message gets overwritten
        # before the player can read it.
        self._outcome_label = QLabel("")
        self._outcome_label.setWordWrap(True)
        layout.addWidget(self._outcome_label)

        self._board_widget = BoardWidget()
        layout.addWidget(self._board_widget)

        self._operation_widget = OperationWidget()
        layout.addWidget(self._operation_widget)

        self._hand_widget = HandWidget()
        layout.addWidget(self._hand_widget)

        self._controls_widget = ControlsWidget()
        layout.addWidget(self._controls_widget)

        self._event_log = EventLogWidget()
        layout.addWidget(self._event_log, stretch=1)

        return page

    # --- Action worker: created on first connect, then lives for the app's lifetime ---

    def _ensure_connected(self, server_address: str) -> None:
        """
        Build the shared channel and the action worker the first time the
        player connects. Called from the lobby handlers rather than from
        __init__, since the server address isn't known until they type it.
        Connecting to a *different* address afterwards isn't supported —
        restart the app for that.
        """
        if self._action_worker is not None:
            return
        self.server_address = server_address
        # Shared gRPC channel — safe to use from multiple stubs/threads.
        self._channel = grpc.insecure_channel(server_address)
        self._setup_action_worker()

    def _setup_action_worker(self) -> None:
        self._action_thread = QThread()
        self._action_worker = GameActionWorker(self._channel)
        self._action_worker.moveToThread(self._action_thread)

        # UI -> worker (queued automatically: sender is on the main thread,
        # receiver lives on _action_thread, so Qt routes each emit through
        # that thread's event loop rather than running it immediately here)
        self._create_game_requested.connect(self._action_worker.create_game)
        self._join_game_requested.connect(self._action_worker.join_game)
        self._start_game_requested.connect(self._action_worker.start_game)
        self._play_turn_requested.connect(self._action_worker.request_play_turn)
        self._discard_requested.connect(self._action_worker.request_discard)
        self._draw_requested.connect(self._action_worker.request_draw)
        self._skip_requested.connect(self._action_worker.request_skip)
        self._leave_requested.connect(self._action_worker.request_leave)
        self._resolve_discard_requested.connect(self._action_worker.request_resolve_discard)

        # Worker -> UI
        self._action_worker.state_updated.connect(self.on_state_updated)
        self._action_worker.turn_result.connect(self.on_turn_result)
        self._action_worker.glitch_events.connect(self.on_glitch_events)
        self._action_worker.action_failed.connect(self.on_action_failed)
        self._action_worker.game_created.connect(self.on_game_created)
        self._action_worker.joined.connect(self.on_joined)

        self._action_thread.start()

    # --- Stream worker: created once we know game_id/player_id ---

    def _start_watching(self, game_id: str, player_id: str) -> None:
        """Call once, right after joining a game."""
        self._stream_thread = QThread()
        self._stream_worker = GameStreamWorker(self._channel, game_id, player_id)
        self._stream_worker.moveToThread(self._stream_thread)

        # Worker -> UI
        self._stream_worker.state_updated.connect(self.on_state_updated)
        self._stream_worker.stream_failed.connect(self.on_action_failed)

        # Start the thread, then kick off the blocking watch loop on it.
        self._stream_thread.started.connect(self._stream_worker.start_watching)
        self._stream_thread.start()

    # --- UI -> worker requests, called from button handlers ---
    # Each emits a signal (see the Signal declarations + connect() calls
    # above) rather than calling the worker directly — that emit is what
    # actually gets routed onto the worker's own thread.

    def request_create_game(self) -> None:
        self._create_game_requested.emit()

    def request_join_game(self, game_id: str, player_name: str) -> None:
        self._join_game_requested.emit({"game_id": game_id, "player_name": player_name})

    def request_start_game(self) -> None:
        self._start_game_requested.emit()

    def request_play_turn(self, objective_index: int, action_indices: list[int]) -> None:
        self._play_turn_requested.emit({
            "objective_index": objective_index,
            "action_indices": action_indices,
        })

    def request_discard(self, card_index: int) -> None:
        self._discard_requested.emit({"card_index": card_index})

    def request_draw(self) -> None:
        self._draw_requested.emit()

    def request_skip(self) -> None:
        self._skip_requested.emit()

    def request_leave(self) -> None:
        self._leave_requested.emit()

    def request_resolve_discard(self, card_indices: list) -> None:
        self._resolve_discard_requested.emit(card_indices)

    # --- Lobby handlers ---

    def _on_create_clicked(self, server_address: str, player_name: str) -> None:
        """
        Create a new game, then join it as its first player. game_created
        (fired by the worker once CreateGame returns) is what actually
        carries the new game_id — request_create_game only sends the
        request, it has no result to read yet.
        """
        self._ensure_connected(server_address)
        self._pending_player_name = player_name
        self._action_worker.game_created.connect(self._on_created_then_join)
        self.request_create_game()

    def _on_created_then_join(self, game_id: str) -> None:
        self._action_worker.game_created.disconnect(self._on_created_then_join)
        self.request_join_game(game_id, self._pending_player_name)

    def _on_join_clicked(self, server_address: str, game_id: str, player_name: str) -> None:
        self._ensure_connected(server_address)
        self._pending_player_name = player_name
        self.game_id = game_id
        self.request_join_game(game_id, player_name)

    # --- Widget click bridges ---
    # ControlsWidget/HandWidget only know "something was clicked/selected" —
    # they don't know about the network layer. These bridges translate
    # that into the appropriate request_* call.

    def _on_play_clicked(self) -> None:
        self._hand_widget.set_mode("play")

    def _on_discard_clicked(self) -> None:
        self._hand_widget.set_mode("discard")

    def _on_play_selection_ready(self, objective_index: int, action_indices: list) -> None:
        self.request_play_turn(objective_index, action_indices)

    def _on_discard_selection_ready(self, card_index: int) -> None:
        self.request_discard(card_index)

    def _on_forced_discard_ready(self, card_indices: list) -> None:
        self.request_resolve_discard(card_indices)

    def _on_selection_changed(self) -> None:
        objective, by_category = self._hand_widget.current_selection()
        self._operation_widget.update_from(objective, by_category)

    # --- Reactive handlers ---

    def on_state_updated(self, state) -> None:
        view = game_state_from_proto(state)
        previous, self._latest_state = self._latest_state, view

        # While the game hasn't started there's nothing for the board or
        # hand to show, so the lobby owns the screen and renders the
        # player list from the same pushes the game page would get.
        if view.status == "lobby":
            self._stack.setCurrentIndex(self.LOBBY_PAGE)
            self._lobby_widget.update_from(view)
            return
        self._stack.setCurrentIndex(self.GAME_PAGE)

        self._log_changes(previous, view)
        self._board_widget.update_from(view)

        me = view.player(self.player_id) if self.player_id else None
        is_my_turn = me is not None and view.current_player_id == self.player_id
        pending = me.pending_discard if me is not None else None
        skip_turn = me.lose_next_turn if me is not None else False
        # A pending discard, or a turn already flagged to be skipped, both
        # block normal turn actions — pending may be left over from this
        # player's own last turn even if it's not currently their turn;
        # skip_turn matters specifically when it IS their turn, since
        # otherwise Play is already disabled by is_my_turn.
        self._controls_widget.set_my_turn(is_my_turn and pending is None and not skip_turn)

        if me is not None:
            self._hand_widget.update_from(me.hand)
            if pending is not None:
                self._hand_widget.set_mode(
                    "discard", count=pending["count"], category=pending["target_category"],
                    reason=pending["reason"],
                )
                self._awaiting_forced_discard = True
            elif self._awaiting_forced_discard:
                self._hand_widget.set_mode("play")
                self._awaiting_forced_discard = False

            if pending is not None and pending["reason"] == "hand_limit":
                note = " — discard down to the 6-card hand limit"
            elif pending is not None:
                note = " — resolve your Glitch Card discard"
            elif is_my_turn and skip_turn:
                note = " — this turn will be skipped"
            elif is_my_turn:
                note = " — your turn!"
            else:
                note = ""
            self._status_label.setText(f"{me.name} (pos {me.board_position}/19){note}")
        else:
            self._status_label.setText(f"Game {view.game_id} — {view.status}")

    def _log_changes(self, previous, view) -> None:
        """
        Turn the difference between two state snapshots into log lines.

        The server only ever pushes whole states, so everything other
        players do has to be inferred by comparing them — there is no event
        stream to subscribe to. A player's own turn is described in more
        detail by on_turn_result, which has the dice and scores.
        """
        # Lobby pushes also populate _latest_state, so the start of play is
        # the status transition rather than the first state we ever see.
        if previous is None or previous.status != "playing":
            self._event_log.append("Game started.", emphasis=True)
            self._announce_turn(view)
            return

        before = {p.id: p for p in previous.players}
        for player in view.players:
            was = before.pop(player.id, None)
            if was is None:
                self._event_log.append(f"{player.name} joined.")
                continue
            moved = player.board_position - was.board_position
            if moved > 0:
                self._event_log.append(
                    f"{player.name} advanced {moved} "
                    f"space{'s' if moved != 1 else ''} to {player.board_position}."
                )
            if player.lose_next_turn and not was.lose_next_turn:
                self._event_log.append(f"{player.name} went offline and misses a turn.")

        for departed in before.values():
            self._event_log.append(f"{departed.name} left the game.")

        if view.winner_id and not previous.winner_id:
            winner = view.player(view.winner_id)
            self._event_log.append(
                f"{winner.name if winner else 'Someone'} reached the centre and wins!",
                emphasis=True,
            )
            return

        if view.current_player_id != previous.current_player_id:
            self._announce_turn(view)

    def _announce_turn(self, view) -> None:
        current = view.player(view.current_player_id)
        if current is None:
            return
        whose = "Your turn." if current.id == self.player_id else f"{current.name}'s turn."
        self._event_log.append(whose)

    def on_turn_result(self, result) -> None:
        if result.glitch_events:
            self.on_glitch_events(list(result.glitch_events))

        if result.lose_turn:
            self._outcome_label.setText(
                f"Operation failed! Responsibility {result.responsibility} — you'll miss your next turn."
            )
        elif not result.success:
            self._outcome_label.setText(
                f"Operation failed. R:{result.responsibility} E:{result.effect} — no movement."
            )
        else:
            moved = result.spaces_moved + (1 if result.bonus else 0)
            bonus_note = " (+1 bonus, drew 2 cards)" if result.bonus else ""
            # A successful but under-responsible operation is held one space
            # short of the centre, so say why rather than letting the player
            # wonder where the rest of their movement went.
            held_note = (
                " Held short of the centre — finishing needs responsibility 3 or more."
                if result.blocked_from_finish else ""
            )
            self._outcome_label.setText(
                f"Success! R:{result.responsibility} E:{result.effect} — "
                f"moved {moved} space(s){bonus_note}.{held_note}"
            )
        self._event_log.append(f"You: {self._outcome_label.text()}")

    def on_glitch_events(self, events: list) -> None:
        """Show one popup per resolved Glitch Card, in order."""
        for event in events:
            self._event_log.append(f"Glitch — {_glitch_log_line(event)}")
            QMessageBox.information(self, "Glitch Card!", _glitch_event_text(event))

    def on_action_failed(self, message: str) -> None:
        # Before the game starts the game page isn't visible, so a failed
        # create/join has to report itself on the lobby screen instead.
        if self._stack.currentIndex() == self.LOBBY_PAGE:
            self._lobby_widget.set_error(message)
        else:
            self._outcome_label.setText(f"Error: {message}")

    def on_game_created(self, game_id: str) -> None:
        self.game_id = game_id

    def on_joined(self, player_id: str) -> None:
        self.player_id = player_id
        self._start_watching(self.game_id, player_id)

    # --- Clean shutdown ---

    def closeEvent(self, event) -> None:
        if self._stream_worker is not None:
            self._stream_worker.stop_watching()
        if self._stream_thread is not None:
            self._stream_thread.quit()
            self._stream_thread.wait()
        if self._action_thread is not None:
            self._action_thread.quit()
            self._action_thread.wait()
        super().closeEvent(event)