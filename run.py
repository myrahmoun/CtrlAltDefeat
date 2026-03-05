#!/usr/bin/evn python3
# -*- coding: utf-8 -*-

'''
Author @Hannah
Created: 01/30/2026
Description: The main script to actually run our game in terminal
'''

import board, cardpile, cards, die, game, operation, player, turn_manager
from datetime import datetime

# Initialize all game components 

def start_game():
    print("Loading...")
    
    date = str(datetime.now())
    official_game = game.Game(date)
    gameboard = board.Board()
    rolling_die = die.Die(6)

    print("All game components created!")
    input("Prese enter to get the game started: ")
    num_players = int(input("How many players will there be?: "))

    if num_players < 2 or num_players > 5: 
        num_players = int(input("Must have between 2-5 players. How many players will there be?: "))

    for player_num in range(num_players):
        player_name = input(f"What is player {player_num + 1}'s name?: ")
        official_game.add_player(player.Player(name=player_name))

    official_game.start_game()

    print("Great! Let the game begin:) ")


if __name__ == "__main__":
    start_game()










