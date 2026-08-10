"""
widgets/hand_widget.py

Displays the current player's hand and handles click-to-select.

Two selection modes, switched via set_mode():
  - "play": select 1 objective + 1 action card per required category (4
    total). Emits play_selection_ready(objective_index, action_indices)
    once a complete, valid selection is made.
  - "discard": select exactly 1 non-objective card. Emits
    discard_selection_ready(card_index) once one is picked.

MainWindow reads these signals and turns them into request_play_turn /
request_discard calls — this widget never talks to the network layer.
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel
from PySide6.QtCore import Signal

REQUIRED_CATEGORIES = {"Intelligence", "Technology", "Governance", "Cybersecurity"}


class HandWidget(QWidget):
    play_selection_ready = Signal(int, list)   # objective_index, action_indices
    discard_selection_ready = Signal(int)      # card_index

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mode = "play"
        self._hand = None  # view_model.HandView
        self._selected_objective_index = None
        self._selected_action_indices = set()

        outer = QVBoxLayout(self)
        self._status_label = QLabel("")
        outer.addWidget(self._status_label)

        self._objective_row = QHBoxLayout()
        outer.addLayout(self._objective_row)
        self._action_row = QHBoxLayout()
        outer.addLayout(self._action_row)

        self._confirm_button = QPushButton("Confirm")
        self._confirm_button.setEnabled(False)
        self._confirm_button.clicked.connect(self._on_confirm_clicked)
        outer.addWidget(self._confirm_button)

    def set_mode(self, mode: str) -> None:
        """mode: 'play' or 'discard'"""
        assert mode in ("play", "discard")
        self._mode = mode
        self._selected_objective_index = None
        self._selected_action_indices = set()
        self._render()

    def update_from(self, hand_view) -> None:
        """hand_view: a view_model.HandView"""
        self._hand = hand_view
        self._selected_objective_index = None
        self._selected_action_indices = set()
        self._render()

    # --- Rendering ---

    def _clear_layout(self, layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def _render(self) -> None:
        self._clear_layout(self._objective_row)
        self._clear_layout(self._action_row)

        if self._hand is None:
            return

        if self._mode == "play":
            for i, card in enumerate(self._hand.objective_cards):
                btn = QPushButton(f"{card.name} (R:{card.responsibility} E:{card.effect})")
                btn.setCheckable(True)
                btn.setChecked(i == self._selected_objective_index)
                btn.clicked.connect(lambda _checked, idx=i: self._toggle_objective(idx))
                self._objective_row.addWidget(btn)

        for i, card in enumerate(self._hand.non_objective_cards):
            label = self._card_label(card)
            btn = QPushButton(label)
            btn.setCheckable(True)
            if self._mode == "play":
                btn.setChecked(i in self._selected_action_indices)
                btn.clicked.connect(lambda _checked, idx=i: self._toggle_action(idx))
            else:  # discard mode
                btn.clicked.connect(lambda _checked, idx=i: self._select_discard(idx))
            self._action_row.addWidget(btn)

        self._update_status_and_confirm()

    def _card_label(self, card) -> str:
        if hasattr(card, "category"):  # ActionCardView
            return f"{card.name} [{card.category}] (R:{card.responsibility} E:{card.effect})"
        return f"{card.name} [GLITCH]"  # GlitchCardView

    # --- Selection logic ---

    def _toggle_objective(self, index: int) -> None:
        self._selected_objective_index = None if self._selected_objective_index == index else index
        self._render()

    def _toggle_action(self, index: int) -> None:
        if index in self._selected_action_indices:
            self._selected_action_indices.discard(index)
        else:
            self._selected_action_indices.add(index)
        self._render()

    def _select_discard(self, index: int) -> None:
        self._selected_objective_index = None
        self._selected_action_indices = {index}
        self._update_status_and_confirm()

    def _selected_categories_valid(self) -> bool:
        if len(self._selected_action_indices) != 4:
            return False
        cards = [self._hand.non_objective_cards[i] for i in self._selected_action_indices]
        categories = {c.category for c in cards if hasattr(c, "category")}
        return categories == REQUIRED_CATEGORIES

    def _update_status_and_confirm(self) -> None:
        if self._mode == "play":
            ready = self._selected_objective_index is not None and self._selected_categories_valid()
            self._status_label.setText(
                "Select 1 objective + 1 card of each category (Intelligence, "
                "Technology, Governance, Cybersecurity)."
            )
            self._confirm_button.setEnabled(ready)
        else:
            ready = len(self._selected_action_indices) == 1
            self._status_label.setText("Select a card to discard.")
            self._confirm_button.setEnabled(ready)

    def _on_confirm_clicked(self) -> None:
        if self._mode == "play":
            self.play_selection_ready.emit(
                self._selected_objective_index, sorted(self._selected_action_indices)
            )
        else:
            (index,) = self._selected_action_indices
            self.discard_selection_ready.emit(index)