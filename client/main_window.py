"""
main_window.py

The visible application window and the only place code runs on the main
thread's Qt event loop (aside from app.py's startup lines).

Owns a GameActionWorker (created immediately, since it needs no game-specific
info to exist) and, once a game is joined, a GameStreamWorker (created only
after game_id/player_id are known). Each worker is moved to its own QThread
here; MainWindow only ever talks to them via signals, never by calling their
methods directly.

Holds the three widgets (board, hand, controls) and is the only place that
translates their clicks into request_* calls, and the only place that
translates incoming GameState/TurnResult protos (via view_model) back into
widget updates.
"""

import grpc
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QLabel

from client.network_worker import GameStreamWorker, GameActionWorker
from client.view_model import game_state_from_proto
from client.widgets.board_widget import BoardWidget
from client.widgets.hand_widget import HandWidget
from client.widgets.controls_widget import ControlsWidget


class MainWindow(QMainWindow):
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

    def __init__(self, server_address: str):
        super().__init__()
        self.server_address = server_address

        # Shared gRPC channel — safe to use from multiple stubs/threads.
        self._channel = grpc.insecure_channel(server_address)

        # Local copies, kept in sync via the joined/game_created signals.
        self.game_id: str | None = None
        self.player_id: str | None = None

        self._setup_action_worker()

        # Created later, once we've joined a game — see _start_watching().
        self._stream_thread: QThread | None = None
        self._stream_worker: GameStreamWorker | None = None

        # Latest translated state, kept so widgets can be re-rendered
        # (e.g. switching HandWidget mode) without waiting for a new push.
        self._latest_state = None

        self._pending_player_name: str | None = None

        self._setup_ui()

    def _setup_ui(self) -> None:
        central = QWidget()
        layout = QVBoxLayout(central)

        self._status_label = QLabel("Not connected.")
        layout.addWidget(self._status_label)

        self._board_widget = BoardWidget()
        layout.addWidget(self._board_widget)

        self._hand_widget = HandWidget()
        layout.addWidget(self._hand_widget)

        self._controls_widget = ControlsWidget()
        layout.addWidget(self._controls_widget)

        self.setCentralWidget(central)

        # Widget -> MainWindow (never widget -> worker directly)
        self._controls_widget.play_clicked.connect(self._on_play_clicked)
        self._controls_widget.draw_clicked.connect(self.request_draw)
        self._controls_widget.discard_clicked.connect(self._on_discard_clicked)
        self._controls_widget.skip_clicked.connect(self.request_skip)
        self._hand_widget.play_selection_ready.connect(self._on_play_selection_ready)
        self._hand_widget.discard_selection_ready.connect(self._on_discard_selection_ready)

    # --- Action worker: exists for the app's whole lifetime ---

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

        # Worker -> UI
        self._action_worker.state_updated.connect(self.on_state_updated)
        self._action_worker.turn_result.connect(self.on_turn_result)
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

    # --- TEMPORARY: stands in for the lobby screen (see widgets/lobby_widget.py) ---

    def auto_join(self, game_id: str, player_name: str) -> None:
        """
        Create a new game if game_id is blank, otherwise join the given
        game_id, using the same request_* signals a real lobby screen
        would use. Once joined, on_joined() -> _start_watching() takes
        over as normal.
        """
        self._pending_player_name = player_name
        if game_id:
            self.request_join_game(game_id, player_name)
        else:
            # game_created (fired by the worker once CreateGame returns)
            # is what actually carries the new game_id — request_create_game
            # only sends the request, it has no result to read yet.
            self._action_worker.game_created.connect(self._on_auto_create_game_created)
            self.request_create_game()

    def _on_auto_create_game_created(self, game_id: str) -> None:
        self._action_worker.game_created.disconnect(self._on_auto_create_game_created)
        self.request_join_game(game_id, self._pending_player_name)

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

    # --- Reactive handlers ---

    def on_state_updated(self, state) -> None:
        view = game_state_from_proto(state)
        self._latest_state = view

        self._board_widget.update_from(view)

        me = view.player(self.player_id) if self.player_id else None
        is_my_turn = me is not None and view.current_player_id == self.player_id
        self._controls_widget.set_my_turn(is_my_turn)

        if me is not None:
            self._hand_widget.update_from(me.hand)
            turn_note = " — your turn!" if is_my_turn else ""
            self._status_label.setText(f"{me.name} (pos {me.board_position}/19){turn_note}")
        else:
            self._status_label.setText(f"Game {view.game_id} — {view.status}")

    def on_turn_result(self, result) -> None:
        if result.lose_turn:
            self._status_label.setText(
                f"Operation failed! Responsibility {result.responsibility} — you'll miss your next turn."
            )
        elif not result.success:
            self._status_label.setText(
                f"Operation failed. R:{result.responsibility} E:{result.effect} — no movement."
            )
        else:
            moved = result.spaces_moved + (1 if result.bonus else 0)
            bonus_note = " (+1 bonus, drew 2 cards)" if result.bonus else ""
            self._status_label.setText(
                f"Success! R:{result.responsibility} E:{result.effect} — moved {moved} space(s){bonus_note}."
            )

    def on_action_failed(self, message: str) -> None:
        self._status_label.setText(f"Error: {message}")

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
        self._action_thread.quit()
        self._action_thread.wait()
        super().closeEvent(event)