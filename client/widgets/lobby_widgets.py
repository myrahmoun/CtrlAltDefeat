"""
widgets/lobby_widget.py

The pre-game screen: connect to a server, create or join a game, watch
other players arrive, and start once there are enough of them.

Like the other widgets, this one knows nothing about the network layer. It
collects input, emits a signal, and re-renders from whatever
GameStateView MainWindow hands back — MainWindow owns every RPC.

Two phases, swapped by _set_phase():
  - "connect" — server address, player name, and an optional game id.
    Leaving the game id blank creates a new game instead of joining one.
  - "waiting" — the joined game's id (to read out to the other players),
    the live player list, and Start Game, enabled only at 3-6 players.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit,
    QPushButton, QListWidget, QGroupBox, QSizePolicy,
)
from PySide6.QtCore import Signal, Qt

MIN_PLAYERS = 3
MAX_PLAYERS = 6

DEFAULT_SERVER = "localhost:50051"


class LobbyWidget(QWidget):
    create_clicked = Signal(str, str)       # server_address, player_name
    join_clicked = Signal(str, str, str)    # server_address, game_id, player_name
    start_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._phase = "connect"

        outer = QVBoxLayout(self)
        outer.setSpacing(14)

        title = QLabel("Ctrl Alt Defeat")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 22px; font-weight: 600;")
        outer.addWidget(title)

        outer.addWidget(self._build_connect_box())
        outer.addWidget(self._build_waiting_box())

        self._status_label = QLabel("")
        self._status_label.setWordWrap(True)
        self._status_label.setAlignment(Qt.AlignCenter)
        outer.addWidget(self._status_label)

        outer.addStretch(1)
        self._set_phase("connect")

    # --- Construction -----------------------------------------------------

    def _build_connect_box(self) -> QGroupBox:
        box = QGroupBox("Connect")
        form = QFormLayout(box)

        self._server_field = QLineEdit(DEFAULT_SERVER)
        self._server_field.setPlaceholderText("host:port, e.g. 192.168.1.10:50051")
        form.addRow("Server", self._server_field)

        self._name_field = QLineEdit()
        self._name_field.setPlaceholderText("required")
        form.addRow("Your name", self._name_field)

        self._game_id_field = QLineEdit()
        self._game_id_field.setPlaceholderText("leave blank to create a new game")
        form.addRow("Game ID", self._game_id_field)

        buttons = QHBoxLayout()
        self._create_button = QPushButton("Create Game")
        self._join_button = QPushButton("Join Game")
        buttons.addWidget(self._create_button)
        buttons.addWidget(self._join_button)
        form.addRow(buttons)

        self._create_button.clicked.connect(self._on_create)
        self._join_button.clicked.connect(self._on_join)
        # Re-evaluate which buttons make sense as the fields change, and let
        # Enter submit whichever action currently applies.
        for field in (self._server_field, self._name_field, self._game_id_field):
            field.textChanged.connect(self._refresh_connect_buttons)
            field.returnPressed.connect(self._on_return_pressed)

        self._connect_box = box
        return box

    def _build_waiting_box(self) -> QGroupBox:
        box = QGroupBox("Waiting for players")
        layout = QVBoxLayout(box)

        self._game_id_label = QLabel("")
        self._game_id_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._game_id_label.setStyleSheet("font-size: 15px;")
        layout.addWidget(self._game_id_label)

        self._player_list = QListWidget()
        self._player_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._player_list.setMinimumHeight(120)
        layout.addWidget(self._player_list)

        self._count_label = QLabel("")
        layout.addWidget(self._count_label)

        self._start_button = QPushButton("Start Game")
        self._start_button.setEnabled(False)
        self._start_button.clicked.connect(self.start_clicked.emit)
        layout.addWidget(self._start_button)

        self._waiting_box = box
        return box

    # --- Phase handling ---------------------------------------------------

    def _set_phase(self, phase: str) -> None:
        self._phase = phase
        self._connect_box.setVisible(phase == "connect")
        self._waiting_box.setVisible(phase == "waiting")
        if phase == "connect":
            self._refresh_connect_buttons()

    # --- Input -> signals -------------------------------------------------

    def _inputs(self):
        return (
            self._server_field.text().strip(),
            self._game_id_field.text().strip(),
            self._name_field.text().strip(),
        )

    def _refresh_connect_buttons(self) -> None:
        server, game_id, name = self._inputs()
        ready = bool(server and name)
        # Creating makes sense only with no game id; joining needs one.
        self._create_button.setEnabled(ready and not game_id)
        self._join_button.setEnabled(ready and bool(game_id))

    def _on_return_pressed(self) -> None:
        if self._join_button.isEnabled():
            self._on_join()
        elif self._create_button.isEnabled():
            self._on_create()

    def _on_create(self) -> None:
        server, _game_id, name = self._inputs()
        self._set_busy("Creating game…")
        self.create_clicked.emit(server, name)

    def _on_join(self) -> None:
        server, game_id, name = self._inputs()
        self._set_busy(f"Joining {game_id}…")
        self.join_clicked.emit(server, game_id, name)

    def _set_busy(self, message: str) -> None:
        """Lock the connect controls while a request is in flight."""
        self._create_button.setEnabled(False)
        self._join_button.setEnabled(False)
        self._status_label.setText(message)

    # --- MainWindow -> widget --------------------------------------------

    def update_from(self, game_state_view) -> None:
        """
        Render the list of joined players and enable Start once there are
        enough. Called for every lobby-status state push, so it also
        doubles as the signal that a create/join actually succeeded.
        """
        self._set_phase("waiting")
        self._game_id_label.setText(
            f"Game ID: <b>{game_state_view.game_id}</b> — share this with the other players"
        )

        self._player_list.clear()
        for i, player in enumerate(game_state_view.players, start=1):
            self._player_list.addItem(f"{i}. {player.name}")

        count = len(game_state_view.players)
        self._start_button.setEnabled(MIN_PLAYERS <= count <= MAX_PLAYERS)

        if count < MIN_PLAYERS:
            need = MIN_PLAYERS - count
            self._count_label.setText(
                f"{count} player{'s' if count != 1 else ''} — "
                f"{need} more needed to start."
            )
        elif count > MAX_PLAYERS:
            self._count_label.setText(f"{count} players — too many, {MAX_PLAYERS} is the limit.")
        else:
            self._count_label.setText(f"{count} players — ready to start.")

        self._status_label.setText("")

    def set_error(self, message: str) -> None:
        """Show a failed create/join and hand the connect controls back."""
        self._status_label.setText(message)
        if self._phase == "connect":
            self._refresh_connect_buttons()
