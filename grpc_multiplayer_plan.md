# gRPC Multiplayer Plan — Ctrl Alt Defeat

## Overview

The goal is to make the game playable across multiple computers by introducing a
client-server architecture using gRPC. One machine hosts the authoritative game
server; every player connects to it as a thin client. The server owns all game
state and logic; clients only send moves and render the state they receive back.

---

## Current Architecture

```
run.py  ──(input())──►  Game  ──►  stdout
```

Everything runs in one process on one terminal. `run.py` interleaves I/O with
game logic — drawing cards, prompting players, and printing results all happen
in the same call stack.

---

## Target Architecture

```
client.py  ──gRPC──►  server.py  ──►  GameEngine
client.py  ──gRPC──►      │
client.py  ──gRPC──►      │
                     streams GameState back to all connected clients
```

- **`server.py`** — wraps the `Game` class, exposes it as a gRPC service
- **`client.py`** — replaces `run.py`, sends moves, renders received state
- **`game.proto`** — defines the shared RPC contract
- **`GameEngine`** — the current `Game` class, stripped of all I/O

---

## Phase 1 — Decouple Logic from I/O

**Goal:** make `Game` (in `refactor.py`) a pure engine with no I/O side effects.

### What to change in `refactor.py`

`execute_turn` currently calls `self.board.display_cards(...)` and
`self.board.clear_card_slots()`. These are display calls and do not belong in
the engine. Remove them and let the client render board state from the
`GameState` it receives.

```python
# Before
def execute_turn(self, player, objective, actions):
    self.board.display_cards(objective, actions)   # ← remove
    result = self._execute_operation(...)
    self.board.clear_card_slots()                  # ← remove
    ...

# After
def execute_turn(self, player, objective, actions):
    result = self._execute_operation(...)
    ...
```

### What to change in `run.py`

`run.py` currently contains:
- Registration logic (`register_players`)
- Card draw / discard enforcement
- `show_hand` display
- `prompt_card_selection` I/O loop
- The main game loop

All of this moves into `client.py`. `run.py` can be kept as a local single-machine
runner (useful for testing), or removed once clients are working.

The card-draw and discard-enforcement steps that `run.py` currently handles need
to move into `server.py`, since the server must be the authority on when cards
are drawn.

---

## Phase 2 — Define the Proto Contract

Create `game.proto` in the project root.

```protobuf
syntax = "proto3";

package beanbag;

// ── RPCs ──────────────────────────────────────────────────────────────────

service BeanBag {
  // Lobby
  rpc CreateGame (CreateGameRequest) returns (GameState);
  rpc JoinGame   (JoinRequest)       returns (JoinResponse);
  rpc StartGame  (StartRequest)      returns (GameState);

  // Gameplay
  rpc GetState   (StateRequest)      returns (GameState);
  rpc PlayTurn   (TurnRequest)       returns (TurnResult);
  rpc DiscardCard(DiscardRequest)    returns (GameState);
  rpc SkipTurn   (SkipRequest)       returns (GameState);

  // Streaming — server pushes updates to all watchers
  rpc WatchGame  (WatchRequest)      returns (stream GameState);
}

// ── Request / Response messages ───────────────────────────────────────────

message CreateGameRequest {}

message JoinRequest {
  string game_id   = 1;
  string player_name = 2;
}

message JoinResponse {
  string player_id = 1;
  GameState state  = 2;
}

message StartRequest {
  string game_id = 1;
}

message StateRequest {
  string game_id = 1;
}

message TurnRequest {
  string game_id          = 1;
  string player_id        = 2;
  int32  objective_index  = 3;       // index into player's objective hand
  repeated int32 action_indices = 4; // 4 indices into player's action hand
}

message TurnResult {
  bool   success       = 1;
  int32  spaces_moved  = 2;
  bool   bonus         = 3;
  bool   lose_turn     = 4;
  int32  responsibility = 5;
  int32  effect        = 6;
  GameState new_state  = 7;
}

message DiscardRequest {
  string game_id     = 1;
  string player_id   = 2;
  int32  card_index  = 3;
}

message SkipRequest {
  string game_id   = 1;
  string player_id = 2;
}

message WatchRequest {
  string game_id = 1;
}

// ── State messages ────────────────────────────────────────────────────────

message GameState {
  string           game_id      = 1;
  string           status       = 2; // "lobby" | "playing" | "finished"
  repeated Player  players      = 3;
  string           current_player_id = 4;
  string           winner_id    = 5;
}

message Player {
  string            id             = 1;
  string            name           = 2;
  int32             board_position = 3;
  bool              lose_next_turn = 4;
  Hand              hand           = 5;
}

message Hand {
  repeated ActionCard    action_cards    = 1;
  repeated ObjectiveCard objective_cards = 2;
}

message ActionCard {
  string name           = 1;
  string description    = 2;
  string category       = 3;
  int32  responsibility = 4;
  int32  effect         = 5;
}

message ObjectiveCard {
  string name           = 1;
  string description    = 2;
  int32  responsibility = 3;
  int32  effect         = 4;
}
```

Generate Python bindings:

```bash
pip install grpcio grpcio-tools
python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. game.proto
# produces: game_pb2.py, game_pb2_grpc.py
```

---

## Phase 3 — Write the Server

Create `server.py`. It holds a dict of active `Game` instances (keyed by
`game_id`) and implements the `BeanBag` servicer.

```python
# server.py  (sketch)
import grpc
import uuid
import queue
from concurrent import futures
from refactor import Game, GameStats
from player import Player as GamePlayer
import game_pb2, game_pb2_grpc

# One queue per game for broadcasting state to watchers
_games: dict[str, Game] = {}
_watchers: dict[str, list[queue.Queue]] = {}


def _to_proto_state(game: Game) -> game_pb2.GameState:
    """Convert internal Game object to proto GameState."""
    ...


class BeanBagServicer(game_pb2_grpc.BeanBagServicer):

    def CreateGame(self, request, context):
        game_id = str(uuid.uuid4())[:8]
        _games[game_id] = Game(game_id)
        _watchers[game_id] = []
        return _to_proto_state(_games[game_id])

    def JoinGame(self, request, context):
        game = _games[request.game_id]
        player = GamePlayer(request.player_name)
        game.players.append(player)
        return game_pb2.JoinResponse(
            player_id=player.id,
            state=_to_proto_state(game)
        )

    def StartGame(self, request, context):
        game = _games[request.game_id]
        game.setup_game()
        _broadcast(request.game_id, game)
        return _to_proto_state(game)

    def PlayTurn(self, request, context):
        game = _games[request.game_id]
        player = _find_player(game, request.player_id)

        # Card draw (was in run.py) now lives here
        for _ in range(2):
            game._refill_if_empty(game.action_pile)
            card = game.action_pile.draw()
            if card and len(player.hand.action_cards) < 6:
                player.hand.action_cards.append(card)

        obj = player.hand.objective_cards[request.objective_index]
        actions = [player.hand.action_cards[i] for i in request.action_indices]

        result = game.execute_turn(player, obj, actions)
        _broadcast(request.game_id, game)
        return game_pb2.TurnResult(**result, new_state=_to_proto_state(game))

    def WatchGame(self, request, context):
        q = queue.Queue()
        _watchers[request.game_id].append(q)
        try:
            while True:
                state = q.get()
                yield state
        finally:
            _watchers[request.game_id].remove(q)


def _broadcast(game_id, game):
    state = _to_proto_state(game)
    for q in _watchers.get(game_id, []):
        q.put(state)


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    game_pb2_grpc.add_BeanBagServicer_to_server(BeanBagServicer(), server)
    server.add_insecure_port('[::]:50051')
    server.start()
    print("Server running on port 50051")
    server.wait_for_termination()
```

---

## Phase 4 — Write the Client

Create `client.py`. It replaces `run.py`. On startup it asks for the server
address, then lets the player join or create a game. A background thread
subscribes to `WatchGame` and re-renders the screen whenever the server sends
a new `GameState`.

```python
# client.py  (sketch)
import grpc
import threading
import game_pb2, game_pb2_grpc

def watch_loop(stub, game_id):
    """Runs in background — prints state whenever server pushes an update."""
    for state in stub.WatchGame(game_pb2.WatchRequest(game_id=game_id)):
        render_state(state)


def render_state(state: game_pb2.GameState):
    print(f"\n[Game {state.game_id}]  Status: {state.status}")
    for p in state.players:
        print(f"  {p.name}: position {p.board_position}/19")
    print(f"  Current turn: {state.current_player_id}")


def main():
    addr = input("Server address (e.g. 192.168.1.10:50051): ")
    channel = grpc.insecure_channel(addr)
    stub = game_pb2_grpc.BeanBagStub(channel)

    game_id = input("Game ID to join (or Enter to create): ").strip()
    if not game_id:
        state = stub.CreateGame(game_pb2.CreateGameRequest())
        game_id = state.game_id
        print(f"Created game: {game_id}")

    name = input("Your name: ")
    join_resp = stub.JoinGame(game_pb2.JoinRequest(game_id=game_id, player_name=name))
    player_id = join_resp.player_id

    # Start background watcher
    t = threading.Thread(target=watch_loop, args=(stub, game_id), daemon=True)
    t.start()

    input("Press Enter when all players have joined, then start the game...")
    stub.StartGame(game_pb2.StartRequest(game_id=game_id))

    # Main turn loop
    while True:
        cmd = input("\n(p)lay / (s)kip / (q)uit: ").strip().lower()
        if cmd == 'q':
            break
        elif cmd == 's':
            stub.SkipTurn(game_pb2.SkipRequest(game_id=game_id, player_id=player_id))
        elif cmd == 'p':
            state = stub.GetState(game_pb2.StateRequest(game_id=game_id))
            me = next(p for p in state.players if p.id == player_id)
            # show hand, prompt indices — same logic as run.py's prompt_card_selection
            ...
            result = stub.PlayTurn(game_pb2.TurnRequest(
                game_id=game_id,
                player_id=player_id,
                objective_index=obj_idx,
                action_indices=action_idxs
            ))
            print_result(result)
```

---

## Phase 5 — Discard Enforcement

The 6-card-max discard loop currently lives in `run.py`. With a server, the
server draws cards (Phase 3) but the client must prompt for discards when the
server's `GameState` shows `len(hand.action_cards) > 6`. Add a helper in
`client.py`:

```python
def maybe_discard(stub, state, player_id, game_id):
    me = next(p for p in state.players if p.id == player_id)
    while len(me.hand.action_cards) > 6:
        show_hand(me)
        idx = int(input("Discard card at index: "))
        state = stub.DiscardCard(game_pb2.DiscardRequest(
            game_id=game_id, player_id=player_id, card_index=idx
        ))
        me = next(p for p in state.players if p.id == player_id)
```

Call this after `PlayTurn` returns and after the server draws bonus cards.

---

## Phase 6 — Player Identity

The current `Player` class in `player.py` has no `id` field — players are
identified by list position. For networked play, add a stable UUID:

```python
# player.py
import uuid

class Player:
    def __init__(self, name: str):
        self.id = str(uuid.uuid4())
        self.name = name
        ...
```

The server uses `player.id` to match incoming `TurnRequest.player_id` against
`game.get_current_player()`.

---

## File Summary

| File | Action |
|---|---|
| `refactor.py` | Remove `board.display_cards` and `board.clear_card_slots` calls from `execute_turn` |
| `player.py` | Add `id = str(uuid.uuid4())` field |
| `game.proto` | Create (new file) |
| `game_pb2.py` / `game_pb2_grpc.py` | Auto-generated from proto |
| `server.py` | Create (new file) — gRPC server wrapping `Game` |
| `client.py` | Create (new file) — replaces `run.py` for networked play |
| `run.py` | Keep as-is for local single-machine testing |

---

## Running the Game

**On the host machine:**
```bash
python server.py
# Server running on port 50051
```

**On each player's machine:**
```bash
python client.py
# Server address: 192.168.1.10:50051
# Your name: Alice
```

All players join using the same `game_id`. The first player to create the game
shares that ID with the others (e.g. over chat). Once everyone has joined, any
player can press Enter to start.

---

## Security Note

`grpc.insecure_channel` transmits data in plaintext — fine for a LAN game
among friends. For play over the internet, replace with
`grpc.ssl_channel_credentials()` and add a TLS certificate to the server.
