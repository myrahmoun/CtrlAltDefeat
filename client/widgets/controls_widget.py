"""
widgets/controls_widget.py

The four top-level turn actions. Each button emits its own signal when
clicked; MainWindow connects these to request_* calls. This widget knows
nothing about the network layer or game rules beyond "is it my turn."
"""

from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton
from PySide6.QtCore import Signal


class ControlsWidget(QWidget):
    play_clicked = Signal()
    draw_clicked = Signal()
    discard_clicked = Signal()
    skip_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)

        self._play_button = QPushButton("Play Turn")
        self._draw_button = QPushButton("Draw Cards")
        self._discard_button = QPushButton("Discard")
        self._skip_button = QPushButton("Skip Turn")

        for btn in (self._play_button, self._draw_button, self._discard_button, self._skip_button):
            layout.addWidget(btn)

        self._play_button.clicked.connect(self.play_clicked.emit)
        self._draw_button.clicked.connect(self.draw_clicked.emit)
        self._discard_button.clicked.connect(self.discard_clicked.emit)
        self._skip_button.clicked.connect(self.skip_clicked.emit)

        self.set_my_turn(False)

    def set_my_turn(self, is_my_turn: bool) -> None:
        """Enable/disable all action buttons based on whether it's this player's turn."""
        for btn in (self._play_button, self._draw_button, self._discard_button, self._skip_button):
            btn.setEnabled(is_my_turn)