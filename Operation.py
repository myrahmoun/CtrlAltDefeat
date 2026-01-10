#!/usr/bin/evn python3
# -*- coding: utf-8 -*-
"""
Created on 12/12/25

@author waldo

"""
import cards, die

class LoseTurnException(Exception):
    def __init__(self):
        super().__init__("Operation failed: lose a turn.")

class InvalidOperationException(Exception):
    def __init__(self):
        super().__init__("Operation is invalid: incomplete or malformed.")

class Operation(object):
    def __init__(self, objective):
        self.objective = objective
        self.intell = None
        self.tech =None
        self.govern = None
        self.cyber = None
        self.responsibility = 0
        self.effect = 0

    def add_action(self, action):
        '''
        Add an ActionCard to the operation. First determine the category of the card,
        and then add to that category. If there is already a card of that category, return
        that card; otherwise return None.
        '''
        return_v = None
        match action.category:
            case 'Intelligence':
                if self.intell is not None:
                    retun_v = self.intell
                self.intell = action
            case 'Technology':
                if self.tech is not None:
                    return_v = self.tech
                self.tech = action
            case 'Governance':
                if self.govern is not None:
                    return_v = self.govern
                self.govern = action
            case 'Cybersecurity':
                if self.cyber is not None:
                    return_v = self.cyber
                self.cyber = action
            case _:
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
        match action.category:
            case 'Intelligence':
                return_v = self.intell
                self.intell = None
            case 'Technology':
                return_v = self.tech
                self.tech = None
            case 'Governance':
                return_v = self.govern
                self.govern = None
            case 'Cybersecurity':
                return_v = self.cyber
                self.cyber = None
            case _:
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

        die_roll = Die.roll()
        if self.responsibility > 3:
            return_val = self.effect
        elif self.responsibility > 0:
            if die_roll < 3:
                return_val = 0
            else:
                return_val = self.effect
        else:
            if die_roll == 6:
                return_val = self.effect
            elif die_roll > 2:
                return_val = 0
            else:
                raise LoseTurnException()
        return return_val
