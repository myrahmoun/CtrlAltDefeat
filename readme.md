# Beanbag — Ctrl Alt Defeat

Terminal-based implementation of the Ctrl Alt Defeat card game. See `instructions.md` for full game rules.

## Play

### Single machine

All players share one terminal:

```bash
python run.py
```

### Multiplayer (LAN)

Each player connects from their own machine over a local network.

**Host machine — start the server:**
```bash
python server.py
```

**Every player (including host) — start a client:**
```bash
python client.py
```

When prompted, enter the host's local IP and port (e.g. `192.168.1.10:50051`). The first player to connect creates a game and shares the game ID with the others. Once everyone has joined, press Enter to start.

Requires Python 3.14. Install dependencies:
```bash
pip install -r requirements.txt
```

After installing, regenerate the gRPC bindings:
```bash
python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. game.proto
```

## Structure

| File | Purpose |
|------|---------|
| `run.py` | Single-machine entry point |
| `refactor.py` | `Game` class — all game logic (setup, turns, card management) |
| `player.py` | `Player` model |
| `cards.py` | `ActionCard`, `ObjectiveCard`, `GlitchCard`, `Hand` |
| `cardpile.py` | `CardPile` — draw, shuffle, refill from discard |
| `board.py` | Board display and card slots |
| `operation.py` | Operation evaluation and scoring |
| `die.py` | Die roll |
| `data/` | Card definitions (JSON) |
| `tests/` | pytest tests |
| `game.proto` | gRPC service and message definitions |
| `server.py` | gRPC server — hosts game state and logic |
| `client.py` | gRPC client — networked player terminal |

## Tests

```bash
pytest tests/
```

Co-authored by Claude Sonnet