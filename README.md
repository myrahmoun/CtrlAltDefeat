# Cyber Operations Board Game

A multiplayer turn-based strategy game where players combine intelligence, technology, governance, and cybersecurity cards to build operations and race to victory on a 20-space board.

## Game Overview

Players compete to be the first to reach position 20 on the game board by successfully executing cyber operations. Each operation requires one objective card and four action cards from different categories. Success depends on the operation's responsibility score and die rolls.

## Current Implementation Status

### Completed Components

**Player Management (`player.py`)**
- Player creation with unique IDs
- Role assignment (agent/adversary)
- Board position tracking
- Hand management for objective and action cards
- Player status states (waiting, playing, finished)

**Card System (`cards.py`)**
- Three card types: ActionCard, ObjectiveCard, GlitchCard
- Action cards have four categories: Intelligence, Technology, Governance, Cybersecurity
- Cards track responsibility and effect scores
- Hand class manages player card collections

**Card Pile Management (`cardpile.py`)**
- Three pile types: action deck, objective deck, discard pile
- Draw, add, and shuffle operations
- Empty pile detection
- Card status tracking

**Board (`board.py`)**
- 20-position track with multiple players per position
- Player movement and position queries
- Card display slots for current operation
- Visual board representation

**Operation Evaluation (`Operation.py`)**
- Combines one objective with four action cards (one per category)
- Calculates total responsibility and effect scores
- Three responsibility tiers:
  - High (>3): automatic success
  - Medium (1-3): die roll determines success
  - Low (≤0): high risk of losing turn
- Returns advancement spaces on success

**Die (`Die.py`)**
- Configurable number of sides
- Random roll generation for turn order and success checks

**Game Controller (`game.py`)**
- Centralized game state management
- Player roster with add/remove functionality
- Card pile initialization
- Turn manager integration
- Game lifecycle structure (waiting, playing, finished)

**Turn Manager (`turn_manager.py`)**
- Framework for turn sequencing
- Turn order tracking with wraparound
- Turn history logging capability

### Pending Implementation

- Turn manager execution logic
- Card dealing at game start
- JSON card loading system
- Deck refill mechanics when empty
- Game state serialization for gRPC
- Victory condition checking
- Glitch card immediate effects
- Timeout handling

## Architecture

### Core Game Loop

1. Players join game (3-6 players required)
2. Cards dealt: 2 objectives + 4 actions per player
3. Die roll determines turn order
4. On each turn:
   - Player selects 1 objective + 4 action cards (one per category)
   - Operation evaluated for success based on responsibility
   - Successful operations advance player by effect score
   - Failed operations result in no movement
   - Played cards discarded, new cards drawn
5. First player to position 20 wins

### Key Game Mechanics

**Responsibility Threshold System**
- High responsibility (>3): Operation succeeds automatically
- Medium responsibility (1-3): Die roll 3+ required for success
- Low responsibility (≤0): Die roll 6 succeeds, 1-2 loses turn, 3-5 no effect

**Card Categories**
All four action categories must be present in an operation:
- Intelligence: Reconnaissance and analysis capabilities
- Technology: Technical tools and infrastructure
- Governance: Policy and authorization framework
- Cybersecurity: Defensive and protective measures

## Project Structure

```
.
├── game.py              # Main game controller
├── player.py            # Player data and state
├── board.py             # Game board and position tracking
├── cards.py             # Card definitions and hand management
├── cardpile.py          # Deck management
├── Operation.py         # Operation evaluation logic
├── Die.py               # Dice rolling
├── turn_manager.py      # Turn sequencing
└── README.md            # This file
```

## Planned Features

### Phase 1: Core Gameplay
- Complete turn management implementation
- Card drawing and dealing mechanics
- JSON-based card definitions
- Basic UI with 2-4 player support

### Phase 2: Multiplayer
- Public matchmaking queue
- Private room creation with invite links
- Real-time game state updates via gRPC streaming
- Player chat system

### Phase 3: Advanced Features
- Vote system for game decisions
- Probability calculator tool
- AI opponents
- Game replay system

## Technology Stack

**Backend**
- Python 3.x
- gRPC for client-server communication
- SQLite for data persistence
- JSON for card definitions

**Frontend** (Planned)
- React with TypeScript
- Pixi.js for board rendering
- gRPC-web for server communication

## Development Notes

Card definitions will be stored in external JSON files to allow balance updates without code changes. The gRPC API will provide services for game management, card operations, state queries, and real-time updates through streaming.

## Authors
HK, JW, MR