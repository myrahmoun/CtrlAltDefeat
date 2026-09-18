"""
Shared fixtures.

Three things need taming before the game is testable:

  - **The die.** `Operation.evaluate_op` builds its own `Die(6)`, so the only
    way to make a turn's outcome predictable is to replace the roll itself.
    The `roll` fixture does that, and every test that exercises a die-gated
    branch uses it rather than seeding `random`.
  - **The server's registry.** `server.server` keeps games in module-level
    dicts, so tests would leak state into each other. The `server` fixture
    clears them on the way out.
  - **Qt.** Widget tests need a QApplication and an offscreen platform, both
    set up once per session. `QT_QPA_PLATFORM` has to be set before Qt is
    imported at all, hence the os.environ line at import time here.
"""

import os
from concurrent import futures
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import src.die as die_module
from src.game import Game
from src.player import Player

MIN_PLAYERS = 3


# ── Core game ─────────────────────────────────────────────────────────────

@pytest.fixture
def roll(monkeypatch):
    """
    Force every die roll to a fixed value: `roll(6)` makes all rolls a 6.
    Patches Die.roll rather than `random`, so it also covers the dice that
    Operation constructs internally.
    """
    def set_roll(value):
        monkeypatch.setattr(die_module.Die, "roll", lambda self: value)
    return set_roll


@pytest.fixture
def make_game():
    """Build a started game with the given player names (3 by default)."""
    def build(*names):
        names = names or ("Alice", "Bob", "Cara")
        game = Game("test-game")
        for name in names:
            game.players.append(Player(name))
        game.setup_game()
        return game
    return build


@pytest.fixture
def game(make_game):
    """A started 3-player game."""
    return make_game()


# ── gRPC server ───────────────────────────────────────────────────────────

@pytest.fixture
def server():
    """
    A real gRPC server on an ephemeral port, with stubs attached. Yields a
    namespace of (lobby, game, address, module) and clears the module's
    game registry afterwards so tests stay independent.
    """
    import grpc
    from proto import basic_pb2_grpc as pb_grpc
    import server.server as server_module

    grpc_server = grpc.server(futures.ThreadPoolExecutor(max_workers=20))
    pb_grpc.add_LobbyServicer_to_server(server_module.LobbyServicer(), grpc_server)
    pb_grpc.add_GameServicer_to_server(server_module.GameServicer(), grpc_server)
    port = grpc_server.add_insecure_port("127.0.0.1:0")
    grpc_server.start()

    address = f"127.0.0.1:{port}"
    channel = grpc.insecure_channel(address)
    yield SimpleNamespace(
        lobby=pb_grpc.LobbyStub(channel),
        game=pb_grpc.GameStub(channel),
        address=address,
        module=server_module,
    )

    channel.close()
    grpc_server.stop(0)
    server_module._games.clear()
    server_module._game_locks.clear()
    server_module._watchers.clear()


@pytest.fixture
def hosted_game(server):
    """
    Create and start a game over gRPC. Yields (game_id, {name: player_id}).
    """
    from proto import basic_pb2 as pb

    def build(*names):
        names = names or ("Alice", "Bob", "Cara")
        game_id = server.lobby.CreateGame(pb.CreateGameRequest()).game_id
        ids = {
            name: server.lobby.JoinGame(
                pb.JoinRequest(game_id=game_id, player_name=name)
            ).player_id
            for name in names
        }
        server.lobby.StartGame(pb.StartRequest(game_id=game_id))
        return game_id, ids
    return build


@pytest.fixture
def lobby_game(server):
    """
    Create a game and join players without starting it, for testing the
    lobby itself. Yields (game_id, {name: player_id}).
    """
    from proto import basic_pb2 as pb

    def build(*names):
        game_id = server.lobby.CreateGame(pb.CreateGameRequest()).game_id
        ids = {
            name: server.lobby.JoinGame(
                pb.JoinRequest(game_id=game_id, player_name=name)
            ).player_id
            for name in names
        }
        return game_id, ids
    return build


# ── Qt ────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def qapp():
    """One QApplication for the whole session — Qt allows only one."""
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def pump(qapp):
    """
    Spin the Qt event loop until `condition` holds or `timeout` elapses,
    returning whether it held. Widget tests need this because the client's
    RPCs run on background QThreads and report back through signals, so
    nothing happens until the main thread processes events.
    """
    import time

    def run(condition, timeout=10.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            qapp.processEvents()
            if condition():
                return True
            time.sleep(0.01)
        qapp.processEvents()
        return bool(condition())
    return run
