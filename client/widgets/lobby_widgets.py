"""
widgets/lobby_widget.py

PLACEHOLDER — not yet wired into MainWindow. For now, game_id/player_name
are collected directly in app.py and MainWindow joins immediately on
startup (see MainWindow.auto_join). This file sketches the intended
shape for when the lobby screen is actually built.

Intended design (see conversation notes):
  - Two modes: "create a new game" or "join an existing game_id".
  - A name field, required before either action is enabled.
  - Once joined: shows the list of players who've joined so far (updated
    from state_updated the same way the game screen reacts to it), plus
    a "Start Game" button enabled once 3-6 players have joined.
  - Emits its own signals (create_clicked, join_clicked(game_id, name),
    start_clicked) — same pattern as ControlsWidget/HandWidget. Never
    talks to the network layer directly.
  - MainWindow holds this widget as page 0 of a QStackedWidget, with the
    existing board/hand/controls group as page 1. MainWindow swaps to
    page 1 once state_updated reports status == "playing".
"""

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Signal


class LobbyWidget(QWidget):
    create_clicked = Signal()
    join_clicked = Signal(str, str)   # game_id, player_name
    start_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        # TODO: build the actual UI (game_id field, name field, player
        # list, create/join/start buttons) when the lobby is implemented.

    def update_from(self, game_state_view) -> None:
        """TODO: render the list of joined players and enable Start once ready."""
        pass