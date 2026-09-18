"""
widgets/operation_widget.py

The operation being built: one slot per card the rulebook requires, plus the
running responsibility and effectiveness totals.

instructions.md, "Building your operation" step 4, tells the player to check
those two scores before committing — so they have to be on screen while the
selection is being made, not after. The widget also spells out what the
totals mean, since the consequence of a given responsibility score is a
table in the rules rather than anything obvious from the number itself.

Read-only. It renders whatever selection HandWidget reports and never
changes it.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QGroupBox,
)
from PySide6.QtCore import Qt

# Display order of the four action slots, left to right.
SLOT_CATEGORIES = ("Intelligence", "Technology", "Governance", "Cybersecurity")

# Mirrors BoardWidget's palette so a category reads the same colour anywhere.
CATEGORY_COLOURS = {
    "Intelligence": "#7F77DD",
    "Technology": "#378ADD",
    "Governance": "#1D9E75",
    "Cybersecurity": "#D85A30",
    "Objective": "#BA7517",
}

EMPTY_TEXT = "—"


class _Slot(QFrame):
    """One labelled card slot: the category, and whatever fills it."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        colour = CATEGORY_COLOURS.get(title, "#8A8778")
        self.setStyleSheet(
            f"QFrame {{ border: 1px solid {colour}; border-radius: 6px; }}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(2)

        heading = QLabel(title)
        heading.setStyleSheet(f"color: {colour}; font-size: 10px; font-weight: 600; border: none;")
        layout.addWidget(heading)

        self._card_label = QLabel(EMPTY_TEXT)
        self._card_label.setWordWrap(True)
        self._card_label.setStyleSheet("border: none;")
        layout.addWidget(self._card_label)

        self._score_label = QLabel("")
        self._score_label.setStyleSheet("color: #6B6858; font-size: 10px; border: none;")
        layout.addWidget(self._score_label)

        layout.addStretch(1)

    def set_card(self, card) -> None:
        if card is None:
            self._card_label.setText(EMPTY_TEXT)
            self._score_label.setText("")
            return
        self._card_label.setText(card.name)
        self._score_label.setText(f"R {card.responsibility:+d}   E {card.effect:+d}")


class OperationWidget(QGroupBox):
    def __init__(self, parent=None):
        super().__init__("Your operation", parent)

        outer = QVBoxLayout(self)

        slots = QHBoxLayout()
        self._slots = {"Objective": _Slot("Objective")}
        slots.addWidget(self._slots["Objective"])
        for category in SLOT_CATEGORIES:
            self._slots[category] = _Slot(category)
            slots.addWidget(self._slots[category])
        outer.addLayout(slots)

        self._totals_label = QLabel()
        self._totals_label.setStyleSheet("font-size: 14px; font-weight: 600;")
        outer.addWidget(self._totals_label)

        self._verdict_label = QLabel()
        self._verdict_label.setWordWrap(True)
        self._verdict_label.setStyleSheet("color: #4A4838;")
        outer.addWidget(self._verdict_label)

        self.clear()

    def clear(self) -> None:
        self.update_from(None, {})

    def update_from(self, objective, cards_by_category: dict) -> None:
        """
        objective: an ObjectiveCardView or None.
        cards_by_category: {category name: ActionCardView} for what's chosen.
        """
        self._slots["Objective"].set_card(objective)
        for category in SLOT_CATEGORIES:
            self._slots[category].set_card(cards_by_category.get(category))

        chosen = [c for c in cards_by_category.values() if c is not None]
        if objective is not None:
            chosen.append(objective)

        # Both totals count every card in the operation, the Objective Card
        # included (instructions.md, "Scoring" steps 1 and 6).
        responsibility = sum(c.responsibility for c in chosen)
        effect = sum(c.effect for c in chosen)

        missing = [c for c in SLOT_CATEGORIES if cards_by_category.get(c) is None]
        if objective is None:
            missing = ["an objective"] + missing

        self._totals_label.setText(
            f"Responsibility {responsibility}   ·   Effectiveness {effect}"
        )
        self._verdict_label.setText(self._verdict(responsibility, effect, missing))

    @staticmethod
    def _verdict(responsibility: int, effect: int, missing: list) -> str:
        if missing:
            return "Still needed: " + ", ".join(missing) + "."

        if responsibility >= 4:
            outcome = (f"Succeeds automatically — {effect} spaces, "
                       "plus a bonus space and two cards.")
        elif responsibility >= 1:
            outcome = f"Needs a die roll of 3 or higher to score {effect}."
        else:
            outcome = (f"Needs a 6 to score {effect}. A 1 or 2 takes you "
                       "offline for a turn.")

        if responsibility < 3:
            outcome += " Not responsible enough to cross the finishing line."
        return outcome
