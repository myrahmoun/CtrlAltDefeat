# Beanbag — Ctrl Alt Defeat

Terminal-based implementation of the Ctrl Alt Defeat card game. See `instructions.md` for full game rules.

## Run

```
python run.py
```

Requires Python 3.14. All players share the same terminal.

## Structure

| File | Purpose |
|------|---------|
| `run.py` | Entry point — handles all terminal I/O and the game loop |
| `refactor.py` | `Game` class — all game logic (setup, turns, card management) |
| `player.py` | `Player` model |
| `cards.py` | `ActionCard`, `ObjectiveCard`, `GlitchCard`, `Hand` |
| `cardpile.py` | `CardPile` — draw, shuffle, refill from discard |
| `board.py` | Board display and card slots |
| `operation.py` | Operation evaluation and scoring |
| `die.py` | Die roll |
| `data/` | Card definitions (JSON) |
| `tests/` | pytest tests |

## Tests

```
pytest tests/
```

Co-authored by Claude Sonnet