# mock_cards_generator.py

# Created 01/13/2026
# author @Myriam

"""
Generate 36 simplified Action cards and 8 simplified objective cards for testing purposes
"""
from typing import List, Optional
import json
import random
import os

NUM_ACT_CARDS_TO_GENERATE = 36
NUM_OBJ_CARDS_TO_GENERATE = 8

# Path for generated JSON files
OUT_PATH = '../data/'

def generate_action_cards(output_path: str, num: int)->None:
    """
    Generate a specified number of action cards at the specified output path
    """
    action_categories = ["Cybersecurity", "Governance", "Intelligence", "Technology"]

    action_cards = []  # Collect all cards here

    for i in range(num):
        category = random.choice(action_categories)  # Random category
        new_card = {
            "name": f"Action Card {i+1}",
            "description": f"A {category} action",
            "category": category, 
            "responsibility": random.randint(0, 3), 
            "effect": random.randint(1, 4) 
        }
        action_cards.append(new_card)

    output_dict = {"cards": action_cards}

    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Write to file
    with open(output_path, 'w') as output:
        json.dump(output_dict, output, indent=2)  # indent=2 for readability
    
    print(f"Generated {num} action cards at {output_path}")

def generate_objective_cards(output_path: str, num: int)-> None:
    """
    Generate a specified number of action cards at the specified output path
    """
    objective_cards = [] # Collect generated cards

    for i in range(num):
        new_card = {
            "name": f"Objective card {i+1}",
            "description": f"Description of objective {i+1}",
            "responsibility": random.randint(0,3),
            "effect": random.randint(1,4)
        }
        objective_cards.append(new_card)
    
    output_dict = {"cards": objective_cards}

    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Write to file
    with open(output_path, 'w') as output:
        json.dump(output_dict, output, indent=2)  # indent=2 for readability
    
    print(f"Generated {num} objective cards at {output_path}")


if __name__ == "__main__":
    # Generate the files
    generate_action_cards(OUT_PATH + "action_cards.json", NUM_ACT_CARDS_TO_GENERATE)
    generate_objective_cards(OUT_PATH + "objective_cards.json", NUM_OBJ_CARDS_TO_GENERATE)
    print("Card generation complete!")