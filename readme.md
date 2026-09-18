# Beanbag — Ctrl Alt Defeat

GUI implementation of the Ctrl Alt Defeat card game, played over a local network.

`instructions.md` has the full game rules, transcribed from the game's own rulebook
(`instructions.pdf`). It also lists, in one place, where this
implementation still diverges from those rules — read that section before changing
anything in `src/`.

## Setup

Requires Python 3.9 or newer (developed on 3.14).

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
python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. proto/basic.proto
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

Each client opens on the lobby screen. Enter the host's address (e.g. `192.168.1.10:50051`) and your player name, then either:

- **Create Game** — starts a new game and shows you its Game ID to pass to the other players, or
- paste an existing **Game ID** and press **Join Game**.

The lobby lists everyone who has joined as they arrive. Once there are 3–6 players, any of them can press **Start Game**.

## Structure

```
root/
├── src/ core game logic, no networking or UI
├── proto/ gRPC service/message definitions and generated bindings
├── server/ gRPC server — hosts game state and logic
├── client/ PySide6 GUI client — networked player app
├── data/ card definitions (JSON), loaded at runtime
├── CardData/ source material — card scans, OCR text, and the authoritative CSVs
└── tests/ pytest suite
```

`data/*.json` is what the game loads; `CardData/` is where it came from. The CSVs
there are the authoritative card values — the `.txt` files are OCR output and read
numbers unreliably.

| File | Purpose |
| ------ | --------- |
| `src/game.py` | `Game` class — setup, turns, card management |
| `src/player.py` | `Player` model |
| `src/cards.py` | `ActionCard`, `ObjectiveCard`, `GlitchCard`, `Hand` (`NonObjectiveCard` is the shared abstract base of `ActionCard`/`GlitchCard`) |
| `src/cardpile.py` | `CardPile` — draw, shuffle, refill from discard |
| `src/board.py` | Board display and card slots |
| `src/operation.py` | Operation evaluation and scoring — sums include the Objective Card |
| `src/die.py` | Die roll |
| `proto/basic.proto` | gRPC service and message definitions |
| `proto/basic_pb2.py`, `proto/basic_pb2_grpc.py` | generated gRPC bindings |
| `server/server.py` | gRPC server — hosts game state and logic, one lock per game |
| `client/app.py` | Entry point — creates the Qt app and window |
| `client/main_window.py` | Main window — owns the network workers and reacts to their signals |
| `client/network_worker.py` | `GameStreamWorker` (long-lived watch stream) and `GameActionWorker` (request/response RPCs), each on its own background thread |
| `client/view_model.py` | Translates proto messages into plain Python view objects for widgets |
| `client/widgets/` | `LobbyWidget` (connect, create/join, player list, start), `BoardWidget`, `HandWidget`, `OperationWidget` (staged cards and running scores), `ControlsWidget`, `EventLogWidget` |
| `data/` | Card definitions (JSON) |
| `instructions.md` | Game rules, plus the list of known divergences from them |
| `CardData/` | Card scans, OCR text, and the source CSVs |

## Tests

```bash
pytest
```

109 tests, about a second. No network or display needed — the Qt tests run
offscreen and the gRPC tests bind an ephemeral loopback port.

| File | Covers |
| ------ | --------- |
| `tests/test_cards.py` | Card parsing, glitch-effect wording, deck composition against `CardData/` |
| `tests/test_operation.py` | Scoring, both die tables, operation completeness |
| `tests/test_game.py` | Setup, turns, the finish rule, glitches, hand limit, pending discards |
| `tests/test_server.py` | Turn ownership, request validation, leaving and disconnecting, full games over gRPC |
| `tests/test_client.py` | View-model translation, widget state, and the lobby driven end to end through three real clients |

`tests/conftest.py` holds the fixtures. Three are worth knowing about: `roll` forces
the die to a fixed value (the only way to make a turn deterministic, since
`Operation` builds its own `Die`), `server` runs a real gRPC server and clears the
module-level game registry afterwards, and `pump` spins the Qt event loop until a
condition holds, which widget tests need because the client's RPCs run on background
threads.

One test is an expected failure: `test_objective_deck_should_hold_24_cards`, marking
the known objective-count bug. It will flip to XPASS when that is fixed.

## Notes

- Action and Glitch cards are both drawn from the same deck and share an abstract
  base class, `NonObjectiveCard`, in `src/cards.py`.
- The fourth action category is printed as **Cyber Intervention** on the cards but is
  named `Cybersecurity` throughout the code, protos, and UI. Same category.
- `Game.FINISH_POSITION` and `Game.MIN_RESPONSIBILITY_TO_FINISH` hold the win
  condition: reach the last space, via an operation with responsibility 3 or more.

## Possible next steps

Not committed to, just recorded so the reasoning isn't lost.

**Host in-process.** Today someone has to run `python server/server.py` separately
and everyone else types in their address. A `server/hosting.py` could start that
same server on a background thread inside a client process, with a "Host a game"
button in the lobby that then connects to `127.0.0.1:<port>` through the ordinary
channel. The client would never learn it is talking to itself, so hosting locally,
joining a machine on the LAN, and one day reaching a hosted server all stay as
different values of a single address — and playing across several windows on one
machine falls out for free.

**A web version.** `src/` has no networking or UI in it, so it would carry over
unchanged along with the ~80 tests that cover it; `server/server.py` would be
rewritten against WebSockets, since browsers cannot speak gRPC without a proxy.
Two things to settle first: reconnection, which does not exist today and which a
page reload makes unavoidable, and whether a *player* can host, given that a
browser tab cannot accept inbound connections without WebRTC or a relay.

Keeping `src/` transport-free is what leaves both of these open.

## Docker

The Dockerfile is the stock VS Code Python scaffold and **does not currently work**.
To build a runnable image it needs, at minimum:

- `CMD` pointing at `server/server.py`, not `server.py`
- `pip install -e .`, so `src`/`proto`/`server` import as packages
- the `grpc_tools.protoc` step from Setup, to generate the bindings
- `EXPOSE 50051` and a matching port mapping in `compose.yaml`
