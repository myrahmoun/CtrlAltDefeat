'''
This file contains the classes for the action, objective, and glitch cards.
Parameters:
    - name: the name of the action card
    - description: the description of the action card
    - respScore: the response score of the action card
    - effectScore: the effect score of the action card
    - category: 
        - "Cybersecurity"
        - "Governance"
        - "Technology"
        - "Intelligence"
    - cardStatus: 
        - in_action_pile
        - in_cache_pile
        - in_objective_pile
        - in_hand
        - in_play
    - glitchType: 
        - Draw 2 action cards
        - Skip turn
        - Discard "n" "category" action cards
        - etc. we can extend this! `
'''

actionCards, objectiveCards, glitchCards = [], [], []
numOfActionCards, numOfObjectiveCards, numOfGlitchCards = 0, 0, 0

class ActionCard:
    '''
    Creates a new action card.
    - Eligible piles: Action, Cache
    - There can be a maximum of 4 action cards in a player's hand.
    '''

    def __init__(self, name, description, category, responsibility, effect):
        self.name = name
        self.description = description
        self.category = category
        self.responsibility = responsibility
        self.effect = effect
        self.cardStatus = "in_action_pile"


        numOfActionCards += 1
        actionCards.append(self)

    def __repr__(self):
        return f"ActionCard(name={self.name}, description={self.description}, category={self.category}, respScore={self.respScore}, effectScore={self.effectScore}, status={self.status})"


class ObjectiveCard:
    '''
    Creates a new objective card.
    - Eligible piles: objective_pile
    - There must be 2 objective cards in a player's hand by the end of each turn.
    '''
    def __init__(self, name, description, responsibility, effect):
        self.name = name
        self.description = description
        self.responsibility = responsibility
        self.effect = effect
        self.cardStatus = "in_objective_pile"

        numOfObjectiveCards += 1
        objectiveCards.append(self)

    def __repr__(self):
        return f"ObjectiveCard(name={self.name}, description={self.description}, respScore={self.respScore}, effectScore={self.effectScore})"

class GlitchCard:
    '''
    Creates a new glitch card.
    - Eligible piles: Action, Cache
    - Glitch cards must be played when drawn. 
    '''
    def __init__(self, name, description, glitchType):
        self.name = name
        self.description = description
        self.glitchType = glitchType
        self.cardStatus = "in_action_pile"

        numOfGlitchCards += 1
        glitchCards.append(self)

    def __repr__(self):
        return f"GlitchCard(name={self.name}, description={self.description}, glitch={self.glitch})"


class Hand:
    '''
    A collection of action and objective cards that each player has. 
    '''
    def __init__(self):
        self.action_cards = []
        self.objective_cards = []

    def __repr__(self):
        return f"Hand(action_cards={self.action_cards}, objective_cards={self.objective_cards})"


    # def addActionCard(self, actionCard):
