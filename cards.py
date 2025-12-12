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
        - etc. we can extend this! 
'''

actionCards, objectiveCards, glitchCards = [], [], []
numOfActionCards, numOfObjectiveCards, numOfGlitchCards = 0, 0, 0

class ActionCard:
    '''
    Creates a new action card.
    - Eligible piles: Action, Cache
    - There can be a maximum of 4 action cards in a player's hand.
    '''

    def __init__(self, name, description, category, respScore, effectScore):
        self.name = name
        self.description = description
        self.category = category
        self.respScore = respScore
        self.effectScore = effectScore
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
    def __init__(self, name, description, respScore, effectScore):
        self.name = name
        self.description = description
        self.respScore = respScore
        self.effectScore = effectScore
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

        for i in range(4): self.action_cards.append(ActionCard())
        for i in range(2): self.objective_cards.append(ObjectiveCard())

    def __repr__(self):
        return f"Hand(action_cards={self.action_cards}, objective_cards={self.objective_cards})"


    # def addActionCard(self, actionCard):

'''
Player Parameters:
    - name: the name of the player
    - role: 
        - "adversary"
        - "agent"
    - hand: the hand of the player with 4 action cards and 2 objective cards
    - boardPosition: the position of the player on the board, also their score. 
    - playerStatus: the status of the player
        - "waiting"
        - "playing"
        - "finished"
'''

class Player:
    def __init__(self, name, role):
        self.name = name
        self.role = role
        self.hand = cards.Hand()
        self.boardPosition = 0
        self.playerStatus = "waiting"

        def __repr__(self):
            return f"Player(name={self.name}, role={self.role}, hand={self.hand}, boardPosition={self.boardPosition}, status={self.status})"

