"""
widgets/board_widget.py

Read-only display of the board: a horizontal track of 20 spaces, each
showing colored tokens for whichever player(s) occupy it. No user
interaction — just redraws whenever told to.
"""

from PySide6.QtWidgets import QWidget, QSizePolicy
from PySide6.QtGui import QPainter, QColor, QFont, QPen
from PySide6.QtCore import Qt, QRectF, QSize

BOARD_SIZE = 20
SPACE_WIDTH = 56
SPACE_HEIGHT = 90
TOKEN_DIAMETER = 28

# A small, distinct palette cycled by player index — flat fills, no gradients.
TOKEN_COLORS = [
    QColor("#378ADD"),  # blue
    QColor("#D85A30"),  # coral
    QColor("#1D9E75"),  # teal
    QColor("#D4537E"),  # pink
    QColor("#BA7517"),  # amber
    QColor("#7F77DD"),  # purple
]


class BoardWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._players = []            # list of view_model.PlayerView
        self._current_player_id = ""
        self._winner_name = ""
        self.setMinimumHeight(SPACE_HEIGHT + 20)
        self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)

    def update_from(self, game_state_view) -> None:
        """game_state_view: a view_model.GameStateView"""
        self._players = game_state_view.players
        self._current_player_id = game_state_view.current_player_id
        winner = game_state_view.player(game_state_view.winner_id) if game_state_view.winner_id else None
        self._winner_name = winner.name if winner else ""
        self.setMinimumWidth(SPACE_WIDTH * BOARD_SIZE)
        self.update()  # trigger a repaint

    def _color_for(self, player_index: int) -> QColor:
        return TOKEN_COLORS[player_index % len(TOKEN_COLORS)]

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        occupants = {i: [] for i in range(BOARD_SIZE)}
        for idx, player in enumerate(self._players):
            pos = min(player.board_position, BOARD_SIZE - 1)
            occupants[pos].append((player, idx))

        for i in range(BOARD_SIZE):
            x = i * SPACE_WIDTH
            space_rect = QRectF(x, 20, SPACE_WIDTH, SPACE_HEIGHT)

            is_current_space = any(
                p.id == self._current_player_id for p, _ in occupants[i]
            )
            painter.setPen(QPen(QColor("#B4B2A9"), 0.5))
            painter.setBrush(QColor("#EEEDFE") if is_current_space else Qt.NoBrush)
            painter.drawRect(space_rect)

            painter.setPen(QColor("#5F5E5A"))
            painter.setFont(QFont(self.font().family(), 9))
            painter.drawText(
                QRectF(x, 4, SPACE_WIDTH, 16), Qt.AlignCenter, str(i+1)
            )

            for slot, (player, player_idx) in enumerate(occupants[i]):
                token_x = x + (SPACE_WIDTH - TOKEN_DIAMETER) / 2
                token_y = 44 + slot * (TOKEN_DIAMETER + 4)
                token_rect = QRectF(token_x, token_y, TOKEN_DIAMETER, TOKEN_DIAMETER)

                color = self._color_for(player_idx)
                painter.setPen(Qt.NoPen)
                painter.setBrush(color)
                painter.drawEllipse(token_rect)

                painter.setPen(QColor("white"))
                painter.setFont(QFont(self.font().family(), 10, QFont.Medium))
                initial = player.name[:1].upper() if player.name else "?"
                painter.drawText(token_rect, Qt.AlignCenter, initial)

                if player.lose_next_turn:
                    painter.setPen(QPen(QColor("#E24B4A"), 2))
                    painter.setBrush(Qt.NoBrush)
                    painter.drawEllipse(token_rect.adjusted(-2, -2, 2, 2))

        if self._winner_name:
            painter.setPen(QColor("#0F6E56"))
            painter.setFont(QFont(self.font().family(), 12, QFont.Medium))
            painter.drawText(
                QRectF(0, SPACE_HEIGHT + 24, self.width(), 20),
                Qt.AlignCenter, f"{self._winner_name} wins!"
            )

    def sizeHint(self):
        return QSize(SPACE_WIDTH * BOARD_SIZE, SPACE_HEIGHT + 20)