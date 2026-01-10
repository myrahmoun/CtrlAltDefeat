# Cyber Operations Board Game

Multiplayer turn-based game where players build cyber operations using Intelligence, Technology, Governance, and Cyber Intervention cards to race across a circular board.

## Overview

Based on the UK National Cyber Force's "Ctrl Alt Defeat" game. Players compete to reach the center of the board first by conducting responsible cyber operations. Balance effectiveness (speed) with responsibility (success chance) to win.

## Game Rules

**Setup:** 3-6 players, each starts with 2 Objective + 4 Action cards  
**Goal:** First player to reach board center wins  
**Turn:** Build operation (1 objective + 4 actions), evaluate success, move forward, draw new cards

**Operation Requirements:**
- 1 Objective Card
- 1 Intelligence Card
- 1 Technology Card
- 1 Governance Card
- 1 Cyber Intervention Card

**Success Determination:**
Total all card responsibility scores (including objective):
- **≥4:** Auto-success, move by total effect + 1 bonus space, draw 2 cards
- **1-3:** Roll die (1-2 fail, 3-6 succeed), move by total effect
- **≤0:** Roll die (1-2 lose turn, 3-5 fail, 6 succeed), move by total effect

**Hand Limits:** Always 2 objectives, up to 6 action cards

## Implementation Status

### Complete
- Player, Card, Board, Die, CardPile classes
- Operation evaluation logic with 3-tier responsibility system
- Basic game and turn manager structure

### In Progress
- Turn execution logic
- JSON card loading
- Card dealing/drawing mechanics
- Victory condition checking

### Todo
- gRPC API layer
- React/Pixi.js frontend
- Glitch card effects
- Advanced rules (Adversary mode, Coalition of Allies)

## Project Structure

```
├── game.py              # Main game controller
├── turn_manager.py      # Turn sequencing and execution
├── player.py            # Player state
├── board.py             # Circular board (20 positions)
├── cards.py             # Card definitions (Action, Objective, Glitch)
├── cardpile.py          # Deck management
├── operation.py         # Operation evaluation and scoring
└── die.py               # Dice rolling
```

## Tech Stack

**Backend:** Python 3.x, gRPC, SQLite  
**Frontend (Planned):** React + TypeScript, Pixi.js  
**Data:** JSON card definitions

## Authors
HK, JW, MR