# Beanbag — Ctrl Alt Defeat

GUI implementation of the Ctrl Alt Defeat card game, played over a local network. See `instructions.md` for full game rules.

## Setup

Requires Python 3.14.

Install dependencies:

```bash
pip install -r requirements.txt
```

Install the project itself in editable mode — this makes `src`, `proto`, `server`, and `client` importable as packages from anywhere in the repo, and only needs to be run once per environment:

```bash
pip install -e .
```

After installing, regenerate the gRPC bindings if `proto/basic.proto` has changed:

```bash
python -m grpc_tools.protoc -I. --python_out=proto --grpc_python_out=proto proto/basic.proto
```

## Play

**Host machine — start the server:**

```bash
python server/server.py
```

**Every player (including host) — start a client:**

```bash
python client/app.py
```

You'll be prompted for the host's local IP and port (e.g. `192.168.1.10:50051`), then a game ID (leave blank to create a new game) and your player name. Once everyone has joined, the host starts the game.

## Structure

```
root/
├── src/ core game logic, no networking or UI
├── proto/ gRPC service/message definitions and generated bindings
├── server/ gRPC server — hosts game state and logic
├── client/ PySide6 GUI client — networked player app
├── data/ card definitions (JSON)
├── tests/ pytest tests
└── docs/ design notes
```

| File | Purpose |
| ------ | --------- |
| `src/game.py` | `Game` class — setup, turns, card management |
| `src/player.py` | `Player` model |
| `src/cards.py` | `ActionCard`, `ObjectiveCard`, `GlitchCard`, `Hand` (`NonObjectiveCard` is the shared abstract base of `ActionCard`/`GlitchCard`) |
| `src/cardpile.py` | `CardPile` — draw, shuffle, refill from discard |
| `src/board.py` | Board display and card slots |
| `src/operation.py` | Operation evaluation and scoring |
| `src/die.py` | Die roll |
| `proto/basic.proto` | gRPC service and message definitions |
| `proto/basic_pb2.py`, `proto/basic_pb2_grpc.py` | generated gRPC bindings |
| `server/server.py` | gRPC server — hosts game state and logic, one lock per game |
| `client/app.py` | Entry point — creates the Qt app and window |
| `client/main_window.py` | Main window — owns the network workers and reacts to their signals |
| `client/network_worker.py` | `GameStreamWorker` (long-lived watch stream) and `GameActionWorker` (request/response RPCs), each on its own background thread |
| `client/view_model.py` | Translates proto messages into plain Python view objects for widgets |
| `client/widgets/` | `BoardWidget`, `HandWidget`, `ControlsWidget`, and the in-progress `LobbyWidget` |
| `data/` | Card definitions (JSON) |
| `tests/` | pytest tests |

## Tests

```bash
pytest tests/
```

NOTE: Action and Glitch cards are both drawn from the same deck and share an abstract base class, `NonObjectiveCard`, in `src/cards.py`.

## Docker

Run `docker build -t beanbag .` to build the container. Untested.
