"""
widgets/hand_widget.py

Displays the current player's hand and handles click-to-select.

Two selection modes, switched via set_mode():
  - "play": select 1 objective + 1 action card per required category (4
    total). Emits play_selection_ready(objective_index, action_indices)
    once a complete, valid selection is made.
  - "discard": select `count` non-objective card(s), optionally restricted
    to one `category`. Emits discard_selection_ready(card_index) for the
    default count=1/no-category voluntary case, or
    forced_discard_ready(card_indices) when `reason` is set (a Glitch Card
    or the hand limit forcing a specific count/category).

MainWindow reads these signals and turns them into request_discard /
request_resolve_discard calls — this widget never talks to the network
layer.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QPushButton, QLabel,
)
from PySide6.QtCore import Signal

REQUIRED_CATEGORIES = {"Intelligence", "Technology", "Governance", "Cybersecurity"}

# The hand caps at six cards, so three per row keeps every label readable
# instead of squeezing six buttons into one row and truncating their names.
CARDS_PER_ROW = 3

_FORCED_DISCARD_PREFIX = {
    "glitch": "Glitch Card: you must discard",
    "hand_limit": "Hand limit: you must discard",
}


class HandWidget(QWidget):
    play_selection_ready = Signal(int, list)           # objective_index, action_indices
    discard_selection_ready = Signal(int)               # card_index
    forced_discard_ready = Signal(list)                 # card_indices
    # Emitted whenever the selection changes, so the operation panel can
    # show the running scores. Carries nothing — read current_selection().
    selection_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mode = "play"
        self._hand = None  # view_model.HandView
        self._selected_objective_index = None
        self._selected_action_indices = set()
        self._discard_count = 1
        self._discard_category = ""
        self._discard_reason = ""  # "" (voluntary) | "glitch" | "hand_limit"

        outer = QVBoxLayout(self)
        self._status_label = QLabel("")
        outer.addWidget(self._status_label)

        self._objective_row = QHBoxLayout()
        outer.addLayout(self._objective_row)
        self._action_row = QGridLayout()
        outer.addLayout(self._action_row)

        self._confirm_button = QPushButton("Confirm")
        self._confirm_button.setEnabled(False)
        self._confirm_button.clicked.connect(self._on_confirm_clicked)
        outer.addWidget(self._confirm_button)

    def set_mode(self, mode: str, *, count: int = 1, category: str = "", reason: str = "") -> None:
        """
        mode: 'play' or 'discard'. count/category/reason only matter for
        'discard': how many cards must be picked, whether they're
        restricted to one category, and (if reason is "glitch" or
        "hand_limit") that confirming emits forced_discard_ready instead of
        discard_selection_ready.
        """
        assert mode in ("play", "discard")
        self._mode = mode
        self._discard_count = count
        self._discard_category = category
        self._discard_reason = reason
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
        """
        Empty a layout of its widgets.

        deleteLater() only schedules destruction for the next event-loop
        pass, and a widget taken out of a layout is still a child of this
        one — so without unparenting it first, the old buttons keep
        painting at their previous geometry underneath the new ones.
        """
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
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
                btn.setChecked(i in self._selected_action_indices)
                if self._discard_category and getattr(card, "category", None) != self._discard_category:
                    btn.setEnabled(False)
                else:
                    btn.clicked.connect(lambda _checked, idx=i: self._select_discard(idx))
            self._action_row.addWidget(btn, i // CARDS_PER_ROW, i % CARDS_PER_ROW)

        self._update_status_and_confirm()
        self.selection_changed.emit()

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
        if index in self._selected_action_indices:
            self._selected_action_indices.discard(index)
        elif len(self._selected_action_indices) < self._discard_count:
            self._selected_action_indices.add(index)
        self._render()

    def current_selection(self):
        """
        What is chosen right now, as (objective_view_or_None, {category: card_view}).
        Resolved here rather than in MainWindow because this widget already
        holds the HandView the indices refer to.
        """
        if self._hand is None or self._mode != "play":
            return None, {}

        objective = None
        if self._selected_objective_index is not None:
            try:
                objective = self._hand.objective_cards[self._selected_objective_index]
            except IndexError:
                objective = None

        by_category = {}
        for index in self._selected_action_indices:
            try:
                card = self._hand.non_objective_cards[index]
            except IndexError:
                continue
            category = getattr(card, "category", None)
            if category is not None:
                by_category[category] = card
        return objective, by_category

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
            ready = len(self._selected_action_indices) == self._discard_count
            category_note = f" {self._discard_category}" if self._discard_category else ""
            plural = "s" if self._discard_count != 1 else ""
            suffix = "" if self._discard_reason else " to discard"  # forced prefixes already say "discard"
            prefix = _FORCED_DISCARD_PREFIX.get(self._discard_reason, "Select")
            self._status_label.setText(
                f"{prefix} {self._discard_count}{category_note} card{plural}{suffix} "
                f"({len(self._selected_action_indices)}/{self._discard_count} selected)."
            )
            self._confirm_button.setEnabled(ready)

    def _on_confirm_clicked(self) -> None:
        if self._mode == "play":
            self.play_selection_ready.emit(
                self._selected_objective_index, sorted(self._selected_action_indices)
            )
        elif self._discard_reason:
            self.forced_discard_ready.emit(sorted(self._selected_action_indices))
        else:
            (index,) = self._selected_action_indices
            self.discard_selection_ready.emit(index)