"""
Define, build and evaluate an operation.
"""
from src.die import Die
import src.cards as cards

class LoseTurnException(Exception):
    def __init__(self):
        super().__init__("Operation failed: lose a turn.")

class InvalidOperationException(Exception):
    def __init__(self):
        super().__init__("Operation is invalid: incomplete or malformed.")

class OperationFailedException(Exception):
    """
    The die roll failed the operation: it scores 0 for effectiveness and the
    player's counter stays put (instructions.md, "Scoring" step 5). Raised
    rather than returning 0, so callers can tell a die failure apart from an
    operation that succeeded but happened to total 0 effectiveness.
    """
    def __init__(self):
        super().__init__("Operation failed: the die roll did not carry it.")

class Operation(object):
    def __init__(self, objective):
        self.objective = objective
        self.intell = None
        self.tech =None
        self.govern = None
        self.cyber = None
        # instructions.md, "Scoring" steps 1 and 6: both totals count every
        # card in the operation, the Objective Card included — so seed them
        # from the objective instead of starting at zero. add_action() then
        # accumulates the four Action Cards on top.
        self.responsibility = objective.responsibility if objective else 0
        self.effect = objective.effect if objective else 0

    def add_action(self, action):
        '''
        Add an ActionCard to the operation. First determine the category of the card,
        and then add to that category. If there is already a card of that category, return
        that card; otherwise return None.
        '''
        return_v = None
        if action.category == cards.CardCategory.INTELLIGENCE:
            if self.intell is not None:
                return_v = self.intell
            self.intell = action
        elif action.category == cards.CardCategory.TECHNOLOGY:
            if self.tech is not None:
                return_v = self.tech
            self.tech = action
        elif action.category == cards.CardCategory.GOVERNANCE:
            if self.govern is not None:
                return_v = self.govern
            self.govern = action
        elif action.category == cards.CardCategory.CYBERSECURITY:
            if self.cyber is not None:
                return_v = self.cyber
            self.cyber = action
        else:
            # unknown category: do nothing (could raise)
            pass
        self.responsibility += action.responsibility
        self.effect += action.effect
        if return_v is not None:
            self.effect -= return_v.effect
            self.responsibility -= return_v.responsibility

        return return_v

    def remove_action(self, action):
        '''
        Remove an ActionCard from the operation based on its category.
        Return the removed card, or None if there was no card of that category.
        '''
        return_v = None
        if action.category == cards.CardCategory.INTELLIGENCE:
            return_v = self.intell
            self.intell = None
        elif action.category == cards.CardCategory.TECHNOLOGY:
            return_v = self.tech
            self.tech = None
        elif action.category == cards.CardCategory.GOVERNANCE:
            return_v = self.govern
            self.govern = None
        elif action.category == cards.CardCategory.CYBERSECURITY:
            return_v = self.cyber
            self.cyber = None
        else:
            # unknown category: do nothing (could raise)
            pass
        return return_v

    def evaluate_op(self):
        '''
        Evaluate the operation by returning the number of spaces to move the player, if any.
        '''
        if (self.cyber is None or
            self.govern is None or
            self.intell is None or
            self.tech is None or
            self.objective is None):
            raise InvalidOperationException

        die_roll = Die(6).roll()
        if self.responsibility > 3:
            return_val = self.effect
        elif self.responsibility > 0:
            if die_roll < 3:
                raise OperationFailedException()
            else:
                return_val = self.effect
        else:
            if die_roll == 6:
                return_val = self.effect
            elif die_roll > 2:
                raise OperationFailedException()
            else:
                raise LoseTurnException()
        return return_val
