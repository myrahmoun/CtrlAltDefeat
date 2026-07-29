"""
Simple class to define and roll a die. 
"""
import random

class Die (object):
    """
    Class representing a die with a given number of sides. Currently the game only requires a six-sided die,
    but this class can be used for other types of dice as well.
    """
    def __init__(self, sides):
        self.sides = sides

    def roll(self):
        return random.randint(1,self.sides)
