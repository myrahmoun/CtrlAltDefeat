"""
widgets/event_log_widget.py

A running account of what has happened in the game.

Around a table, players describe their operation aloud as they play it
(instructions.md, "Playing an operation" step 1). Over the network there is
no equivalent, so without a log a player sees other people's counters move
with no idea why. MainWindow derives entries by diffing successive game
states and feeds them here.
"""

from PySide6.QtWidgets import QGroupBox, QVBoxLayout, QListWidget, QListWidgetItem
from PySide6.QtCore import Qt

MAX_ENTRIES = 200


class EventLogWidget(QGroupBox):
    def __init__(self, parent=None):
        super().__init__("Game log", parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        self._list = QListWidget()
        self._list.setAlternatingRowColors(True)
        self._list.setWordWrap(True)
        self._list.setSelectionMode(QListWidget.NoSelection)
        self._list.setFocusPolicy(Qt.NoFocus)
        layout.addWidget(self._list)

    def append(self, message: str, emphasis: bool = False) -> None:
        item = QListWidgetItem(message)
        if emphasis:
            font = item.font()
            font.setBold(True)
            item.setFont(font)
        self._list.addItem(item)

        # Keep the list bounded; a long game would otherwise grow without end.
        while self._list.count() > MAX_ENTRIES:
            self._list.takeItem(0)

        self._list.scrollToBottom()

    def entries(self) -> list:
        return [self._list.item(i).text() for i in range(self._list.count())]

    def clear(self) -> None:
        self._list.clear()
