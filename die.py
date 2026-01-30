#!/usr/bin/evn python3
# -*- coding: utf-8 -*-
"""
Created on 12/12/25

@author waldo

"""
import random

class Die (object):
    '''
    Class representing a die with a given number of sides. Currently the game only requires a six-sided die,
    but this class can be used for other types of dice as well.
    '''
    def __init__(self, sides):
        self.sides = sides

    def roll(self):
        return random.randint(1,self.sides)
