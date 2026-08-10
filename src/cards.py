"""
cards.py
Objective and non-objective card classes, plus Hand.
"""

from abc import ABC, abstractmethod
from enum import Enum
import re


class CardStatus(Enum):
    IN_NON_OBJECTIVE = "in_non_objective_pile"
    IN_CACHE_PILE = "in_cache_pile"
    IN_OBJECTIVE_PILE = "in_objective_pile"
    IN_HAND = "In_hand"
    IN_PLAY = "in_play"
    IN_DISCARD_PILE = "in_discard_pile"


class CardCategory(str, Enum):
    CYBERSECURITY = "Cybersecurity"
    GOVERNANCE = "Governance"
    TECHNOLOGY = "Technology"
    INTELLIGENCE = "Intelligence"
    GLITCH = "Glitch"


class GlitchEffectType(str, Enum):
    """Effect a glitch card triggers when drawn: discard, draw, or skip an operation."""
    DISCARD = "discard"
    DRAW = "draw"
    SKIP_OPERATION = "skip_operation"


class NonObjectiveCard(ABC):
    """
    Abstract base for cards drawn from the action/non-objective deck.
    Holds only what ActionCard and GlitchCard share. Not instantiable directly.
    """

    def __init__(self, name, description):
        self.name = name
        self.description = description
        self.cardStatus = CardStatus.IN_NON_OBJECTIVE

    @property
    @abstractmethod
    def category(self) -> CardCategory:
        raise NotImplementedError

    def __repr__(self):
        return (f"{self.__class__.__name__}(name={self.name}, "
                f"description={self.description}, status={self.cardStatus})")


class ActionCard(NonObjectiveCard):
    """Intelligence, Technology, Governance, or Cyber Intervention card; played into an Operation."""

    def __init__(self, name, description, category: CardCategory, responsibility=0, effect=0):
        super().__init__(name, description)
        if category == CardCategory.GLITCH:
            raise ValueError("ActionCard cannot have category GLITCH; use GlitchCard instead")
        self._category = category
        self.responsibility = responsibility
        self.effect = effect

    @property
    def category(self) -> CardCategory:
        return self._category

    @classmethod
    def from_json(cls, data: dict) -> "ActionCard":
        """Build an ActionCard from a raw JSON card entry, defaulting blank responsibility/effect to 0."""
        return cls(
            name=data['name'],
            description=data['description'],
            category=data['category'],
            responsibility=data['responsibility'] if data['responsibility'] != "" else 0,
            effect=data['effect'] if data['effect'] != "" else 0,
        )

    def __repr__(self):
        return (f"ActionCard(name={self.name}, category={self.category}, "
                f"respScore={self.responsibility}, effectScore={self.effect}, "
                f"status={self.cardStatus})")


class GlitchCard(NonObjectiveCard):
    """
    Must be played immediately when drawn; resolving it may draw further
    glitches, which must also be played immediately.
    """

    def __init__(self, name, description, glitchType,
                 effect_type: GlitchEffectType, target_category=None, count=1):
        super().__init__(name, description)
        self.glitchType = glitchType
        self.effect_type = effect_type
        self.target_category = target_category
        self.count = count

    @property
    def category(self) -> CardCategory:
        return CardCategory.GLITCH


    @classmethod
    def from_json(cls, data: dict) -> "GlitchCard":
        """Build a GlitchCard from a raw JSON card entry, parsing glitchType."""
        glitch_type = data["glitchType"]
        effect_type, target_category, count = cls._parse_glitch_type(glitch_type)
        return cls(
            name=data["name"],
            description=data["description"],
            glitchType=glitch_type,
            effect_type=effect_type,
            target_category=target_category,
            count=count,
        )

    @staticmethod
    def _parse_glitch_type(glitch_type_str: str):
        """Parse a glitchType string into (effect_type, target_category, count)."""
        s = glitch_type_str.strip()

        if "cannot complete an operation" in s.lower():
            return GlitchEffectType.SKIP_OPERATION, None, 1

        m = re.match(r"Draw (\d+) Action Cards?", s, re.IGNORECASE)
        if m:
            return GlitchEffectType.DRAW, None, int(m.group(1))

        m = re.match(r"Discard (\d+) (\w+) Cards?", s, re.IGNORECASE)
        if m:
            count = int(m.group(1))
            category_word = m.group(2)
            if category_word.lower() == "action":
                return GlitchEffectType.DISCARD, None, count
            try:
                target_category = CardCategory(category_word.capitalize())
            except ValueError:
                raise ValueError(f"Unknown discard category in glitchType: {s!r}")
            return GlitchEffectType.DISCARD, target_category, count

        raise ValueError(f"Unrecognized glitchType string: {s!r}")


    def __repr__(self):
        return (f"GlitchCard(name={self.name}, effect_type={self.effect_type}, "
                f"target_category={self.target_category}, count={self.count}, "
                f"status={self.cardStatus})")


class ObjectiveCard:
    """Task card players fulfil to move around the board. Max 2 held at once."""

    def __init__(self, name, description, responsibility, effect):
        self.name = name
        self.description = description
        self.responsibility = responsibility
        self.effect = effect
        self.cardStatus = CardStatus.IN_OBJECTIVE_PILE

    @classmethod
    def from_json(cls, data: dict) -> "ObjectiveCard":
        """Build an ObjectiveCard from a raw JSON card entry."""
        return cls(
            name=data['name'],
            description=data['description'],
            responsibility=data['responsibility'],
            effect=data['effect'],
        )

    def __repr__(self):
        return (f"ObjectiveCard(name={self.name}, respScore={self.responsibility}, "
                f"effectScore={self.effect}, status={self.cardStatus})")


class Hand:
    """A player's non-objective and objective cards."""

    def __init__(self):
        self.non_objective_cards = []
        self.objective_cards = []

    def __repr__(self):
        return f"Hand(non_objective_cards={self.non_objective_cards}, objective_cards={self.objective_cards})"