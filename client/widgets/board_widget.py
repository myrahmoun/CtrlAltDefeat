"""
widgets/board_widget.py

Read-only display of the board: a track of 20 spaces, each showing colored
tokens for whichever player(s) occupy it. No user interaction — just
redraws whenever told to.

The track reflows into as many rows as the widget's current width allows
(like wrapped text), snaking left-to-right then right-to-left row over row,
so it stays readable at any window size instead of forcing horizontal
scrolling. Tokens sharing a space are packed into a small grid that shrinks
to fit rather than spilling past the space's edges.
"""

from PySide6.QtWidgets import QWidget, QSizePolicy
from PySide6.QtGui import QPainter, QColor, QFont, QPen
from PySide6.QtCore import Qt, QRectF, QSize

BOARD_SIZE = 20
SPACE_WIDTH = 64
SPACE_HEIGHT = 78
LABEL_HEIGHT = 20
ROW_GAP = 22
TOP_MARGIN = 4
BOTTOM_MARGIN = 30
CELL_PAD = 3

TOKEN_DIAMETER_MAX = 26
TOKEN_DIAMETER_MIN = 12
TOKEN_GAP = 3
TOKEN_AREA_PAD = 6

BOARD_BG = QColor("#F7F6F1")
SPACE_BORDER = QColor("#C7C4B8")
SPACE_FILL_EVEN = QColor("#FFFFFF")
SPACE_FILL_ODD = QColor("#F1F0E9")
CURRENT_SPACE_FILL = QColor("#E4E9FB")
CURRENT_SPACE_BORDER = QColor("#7C8CE0")
START_FINISH_FILL = QColor("#E8F3EC")

# A small, distinct palette cycled by player index — flat fills, no gradients.
TOKEN_COLORS = [
    QColor("#378ADD"),  # blue
    QColor("#D85A30"),  # coral
    QColor("#1D9E75"),  # teal
    QColor("#D4537E"),  # pink
    QColor("#BA7517"),  # amber
    QColor("#7F77DD"),  # purple
]


def _fit_tokens(count: int, avail_w: float, avail_h: float):
    """
    Pick the (diameter, columns, rows) grid that packs `count` tokens into
    avail_w x avail_h as large as possible, never exceeding TOKEN_DIAMETER_MAX
    and never shrinking below TOKEN_DIAMETER_MIN (tokens may overlap slightly
    at extreme counts rather than vanish).
    """
    best = (TOKEN_DIAMETER_MIN, 1, count)
    for cols in range(1, count + 1):
        rows = -(-count // cols)  # ceil division
        d_w = (avail_w - (cols - 1) * TOKEN_GAP) / cols
        d_h = (avail_h - (rows - 1) * TOKEN_GAP) / rows
        d = min(TOKEN_DIAMETER_MAX, d_w, d_h)
        if d > best[0]:
            best = (d, cols, rows)
    return best


class BoardWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._players = []            # list of view_model.PlayerView
        self._current_player_id = ""
        self._winner_name = ""

        policy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)

    def update_from(self, game_state_view) -> None:
        """game_state_view: a view_model.GameStateView"""
        self._players = game_state_view.players
        self._current_player_id = game_state_view.current_player_id
        winner = game_state_view.player(game_state_view.winner_id) if game_state_view.winner_id else None
        self._winner_name = winner.name if winner else ""
        self.updateGeometry()  # width->height mapping may have changed row count
        self.update()

    def _color_for(self, player_index: int) -> QColor:
        return TOKEN_COLORS[player_index % len(TOKEN_COLORS)]

    # --- Responsive row-wrapping layout -----------------------------------

    def _spaces_per_row(self, width: int) -> int:
        return max(1, min(BOARD_SIZE, int(width) // SPACE_WIDTH))

    def _row_count(self, width: int) -> int:
        per_row = self._spaces_per_row(width)
        return -(-BOARD_SIZE // per_row)  # ceil division

    def _row_pitch(self) -> int:
        return LABEL_HEIGHT + SPACE_HEIGHT + ROW_GAP

    def heightForWidth(self, width: int) -> int:
        rows = self._row_count(max(width, SPACE_WIDTH))
        return TOP_MARGIN + rows * self._row_pitch() - ROW_GAP + BOTTOM_MARGIN

    def sizeHint(self):
        w = SPACE_WIDTH * min(BOARD_SIZE, 10)
        return QSize(w, self.heightForWidth(w))

    def minimumSizeHint(self):
        w = SPACE_WIDTH * 3
        return QSize(w, self.heightForWidth(w))

    def _space_rect(self, index: int, per_row: int) -> tuple[QRectF, bool]:
        """Returns (rect, row_is_reversed) for board space `index` under the current width."""
        row, col = divmod(index, per_row)
        reversed_row = row % 2 == 1
        visual_col = (per_row - 1 - col) if reversed_row else col
        x = visual_col * SPACE_WIDTH + CELL_PAD
        y = TOP_MARGIN + LABEL_HEIGHT + row * self._row_pitch()
        return QRectF(x, y, SPACE_WIDTH - 2 * CELL_PAD, SPACE_HEIGHT), reversed_row

    # --- Painting -----------------------------------------------------------

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), BOARD_BG)

        per_row = self._spaces_per_row(self.width())

        occupants = {i: [] for i in range(BOARD_SIZE)}
        for idx, player in enumerate(self._players):
            pos = min(player.board_position, BOARD_SIZE - 1)
            occupants[pos].append((player, idx))

        for i in range(BOARD_SIZE):
            space_rect, reversed_row = self._space_rect(i, per_row)
            is_current_space = any(p.id == self._current_player_id for p, _ in occupants[i])
            is_endpoint = i == 0 or i == BOARD_SIZE - 1

            if is_current_space:
                fill, border = CURRENT_SPACE_FILL, CURRENT_SPACE_BORDER
            elif is_endpoint:
                fill, border = START_FINISH_FILL, SPACE_BORDER
            else:
                fill = SPACE_FILL_EVEN if i % 2 == 0 else SPACE_FILL_ODD
                border = SPACE_BORDER

            painter.setPen(QPen(border, 1.2 if is_current_space else 0.6))
            painter.setBrush(fill)
            painter.drawRoundedRect(space_rect, 8, 8)

            painter.setPen(QColor("#8A8778"))
            painter.setFont(QFont(self.font().family(), 8, QFont.DemiBold))
            label = "START" if i == 0 else "FINISH" if i == BOARD_SIZE - 1 else str(i + 1)
            painter.drawText(
                QRectF(space_rect.x(), space_rect.y() - LABEL_HEIGHT, space_rect.width(), LABEL_HEIGHT - 2),
                Qt.AlignCenter, label,
            )

            self._draw_row_connector(painter, i, per_row, space_rect, reversed_row)
            self._draw_tokens(painter, space_rect, occupants[i])

        rows = self._row_count(self.width())
        if self._winner_name:
            y = TOP_MARGIN + rows * self._row_pitch() - ROW_GAP + 6
            painter.setPen(QColor("#0F6E56"))
            painter.setFont(QFont(self.font().family(), 12, QFont.Medium))
            painter.drawText(QRectF(0, y, self.width(), 20), Qt.AlignCenter, f"{self._winner_name} wins!")

    def _draw_row_connector(self, painter, index, per_row, space_rect, reversed_row) -> None:
        """
        A short curved stub linking the last space of a row to the first
        space of the next, so the snake path reads as one continuous track
        instead of unrelated rows.
        """
        is_row_end = (index % per_row == per_row - 1) or (index == BOARD_SIZE - 1)
        if not is_row_end or index == BOARD_SIZE - 1:
            return
        painter.setPen(QPen(SPACE_BORDER, 1.4))
        painter.setBrush(Qt.NoBrush)
        edge_x = space_rect.right() if not reversed_row else space_rect.left()
        y1 = space_rect.bottom() - 6
        y2 = space_rect.bottom() + ROW_GAP + 6
        painter.drawLine(int(edge_x), int(y1), int(edge_x), int(y2))

    def _draw_tokens(self, painter, space_rect, occupants) -> None:
        if not occupants:
            return
        avail_w = space_rect.width() - 2 * TOKEN_AREA_PAD
        avail_h = space_rect.height() - 2 * TOKEN_AREA_PAD
        diameter, cols, rows = _fit_tokens(len(occupants), avail_w, avail_h)

        grid_w = cols * diameter + (cols - 1) * TOKEN_GAP
        grid_h = rows * diameter + (rows - 1) * TOKEN_GAP
        origin_x = space_rect.x() + (space_rect.width() - grid_w) / 2
        origin_y = space_rect.y() + (space_rect.height() - grid_h) / 2

        for slot, (player, player_idx) in enumerate(occupants):
            col, row = slot % cols, slot // cols
            token_x = origin_x + col * (diameter + TOKEN_GAP)
            token_y = origin_y + row * (diameter + TOKEN_GAP)
            token_rect = QRectF(token_x, token_y, diameter, diameter)

            painter.setPen(Qt.NoPen)
            painter.setBrush(self._color_for(player_idx))
            painter.drawEllipse(token_rect)

            painter.setPen(QColor("white"))
            font_size = max(7, int(diameter * 0.42))
            painter.setFont(QFont(self.font().family(), font_size, QFont.Medium))
            initial = player.name[:1].upper() if player.name else "?"
            painter.drawText(token_rect, Qt.AlignCenter, initial)

            if player.lose_next_turn:
                painter.setPen(QPen(QColor("#E24B4A"), 2))
                painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(token_rect.adjusted(-2, -2, 2, 2))
