"""
widgets/board_widget.py

Read-only display of the board: 20 spaces, each showing which player(s)
occupy it. No user interaction — just redraws whenever told to.
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

BOARD_SIZE = 20


class BoardWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self._space_labels = []
        for i in range(BOARD_SIZE):
            label = QLabel(f"{i:2d}: [ ]")
            layout.addWidget(label)
            self._space_labels.append(label)
        self._winner_label = QLabel("")
        layout.addWidget(self._winner_label)

    def update_from(self, game_state_view) -> None:
        """game_state_view: a view_model.GameStateView"""
        occupants = {i: [] for i in range(BOARD_SIZE)}
        for player in game_state_view.players:
            pos = min(player.board_position, BOARD_SIZE - 1)
            label = player.name
            if player.id == game_state_view.current_player_id:
                label += "*"
            if player.lose_next_turn:
                label += "!"
            occupants[pos].append(label)

        for i, label in enumerate(self._space_labels):
            names = occupants[i]
            text = f"{i:2d}: [{', '.join(names)}]" if names else f"{i:2d}: [ ]"
            label.setText(text)

        if game_state_view.winner_id:
            winner = game_state_view.player(game_state_view.winner_id)
            self._winner_label.setText(f"*** {winner.name} wins! ***" if winner else "")
        else:
            self._winner_label.setText("")