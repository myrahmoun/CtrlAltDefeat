"""
network_worker.py

Owns all gRPC traffic for the client, split across two QObjects that will
each live on their own background QThread:

  - GameStreamWorker: runs the WatchGame stream. Each loop iteration blocks
    until the next server update. A thread shared with this loop would be unavailable
    for the duration of each gap between states, so queued requests (e.g. button clicks)
    could stall until the next update arrives. Runs on its own thread so
    nothing is ever queued behind it.

  - GameActionWorker: handles every other RPC (PlayTurn, DiscardCard,
    DrawCards, SkipTurn, LeaveGame, plus the one-off lobby calls). Each of
    these is a quick request/response, so they can all share one thread
    and respond promptly to requests as they arrive.

Neither class touches the UI directly — only Qt signals cross the thread
boundary, in both directions.
"""
import grpc
from PySide6.QtCore import QObject, Signal, Slot
 
from proto import basic_pb2 as pb
from proto import basic_pb2_grpc as pb_grpc
 
 
class GameStreamWorker(QObject):
    """Lives on its own thread. Blocks inside start_watching() for the game's duration."""
 
    state_updated = Signal(object)   # carries a pb.GameState
    stream_failed = Signal(str)
 
    def __init__(self, channel: grpc.Channel, game_id: str, player_id: str):
        super().__init__()
        self._stub = pb_grpc.LobbyStub(channel)
        self.game_id = game_id
        self.player_id = player_id
        self._watching = False
        self._call = None  # the in-flight streaming call, so stop_watching() can cancel it
 
    @Slot()
    def start_watching(self) -> None:
        """Blocks this thread until the stream ends. Call once, right after this object's thread starts."""
        self._watching = True
        self._call = self._stub.WatchGame(
            pb.WatchRequest(game_id=self.game_id, player_id=self.player_id)
        )
        try:
            for state in self._call:
                if not self._watching:
                    break
                self.state_updated.emit(state)
        except grpc.RpcError as e:
            if self._watching:  # don't report an error if we intentionally stopped
                self.stream_failed.emit(f"Lost connection to game: {e.details()}")

    def stop_watching(self) -> None:
        """Cancel the in-flight stream so start_watching()'s blocking loop actually unblocks."""
        self._watching = False
        if self._call is not None:
            self._call.cancel()
 
 
class GameActionWorker(QObject):
    """Lives on its own thread. Handles every request/response RPC."""
 
    # --- Outgoing: worker -> UI ---
    state_updated = Signal(object)      # carries a pb.GameState
    turn_result = Signal(object)        # carries a pb.TurnResult
    glitch_events = Signal(object)      # carries a list of pb.GlitchEvent
    action_failed = Signal(str)
    game_created = Signal(str)          # carries the new game_id
    joined = Signal(str)                # carries the assigned player_id
 
    def __init__(self, channel: grpc.Channel):
        super().__init__()
        self._lobby_stub = pb_grpc.LobbyStub(channel)
        self._game_stub = pb_grpc.GameStub(channel)
        self.game_id = None
        self.player_id = None
 
    # --- Lobby ---
 
    @Slot()
    def create_game(self) -> None:
        try:
            state = self._lobby_stub.CreateGame(pb.CreateGameRequest())
            self.game_id = state.game_id
            self.game_created.emit(state.game_id)
            self.state_updated.emit(state)
        except grpc.RpcError as e:
            self.action_failed.emit(f"Couldn't create game: {e.details()}")
 
    @Slot(dict)
    def join_game(self, payload: dict) -> None:
        """payload: {"game_id": str, "player_name": str}"""
        try:
            resp = self._lobby_stub.JoinGame(pb.JoinRequest(
                game_id=payload["game_id"], player_name=payload["player_name"]
            ))
            self.game_id = payload["game_id"]
            self.player_id = resp.player_id
            self.joined.emit(resp.player_id)
            self.state_updated.emit(resp.state)
        except grpc.RpcError as e:
            self.action_failed.emit(f"Couldn't join game: {e.details()}")
 
    @Slot()
    def start_game(self) -> None:
        try:
            state = self._lobby_stub.StartGame(pb.StartRequest(game_id=self.game_id))
            self.state_updated.emit(state)
        except grpc.RpcError as e:
            self.action_failed.emit(f"Couldn't start game: {e.details()}")
 
    # --- In-game actions ---
 
    @Slot(dict)
    def request_play_turn(self, payload: dict) -> None:
        """payload: {"objective_index": int, "action_indices": list[int]}"""
        try:
            result = self._game_stub.PlayTurn(pb.TurnRequest(
                game_id=self.game_id, player_id=self.player_id,
                objective_index=payload["objective_index"],
                action_indices=payload["action_indices"],
            ))
            self.turn_result.emit(result)
            self.state_updated.emit(result.new_state)
        except grpc.RpcError as e:
            self.action_failed.emit(f"Couldn't play turn: {e.details()}")
 
    @Slot(dict)
    def request_discard(self, payload: dict) -> None:
        """payload: {"card_index": int}"""
        try:
            state = self._game_stub.DiscardCard(pb.DiscardRequest(
                game_id=self.game_id, player_id=self.player_id,
                card_index=payload["card_index"],
            ))
            self.state_updated.emit(state)
        except grpc.RpcError as e:
            self.action_failed.emit(f"Couldn't discard: {e.details()}")
 
    @Slot()
    def request_draw(self) -> None:
        try:
            result = self._game_stub.DrawCards(pb.DrawRequest(
                game_id=self.game_id, player_id=self.player_id,
            ))
            if result.glitch_events:
                self.glitch_events.emit(list(result.glitch_events))
            self.state_updated.emit(result.new_state)
        except grpc.RpcError as e:
            self.action_failed.emit(f"Couldn't draw: {e.details()}")

    @Slot(list)
    def request_resolve_discard(self, card_indices: list) -> None:
        try:
            result = self._game_stub.ResolveDiscard(pb.ResolveDiscardRequest(
                game_id=self.game_id, player_id=self.player_id, card_indices=card_indices,
            ))
            if result.glitch_events:
                self.glitch_events.emit(list(result.glitch_events))
            self.state_updated.emit(result.new_state)
        except grpc.RpcError as e:
            self.action_failed.emit(f"Couldn't resolve discard: {e.details()}")
 
    @Slot()
    def request_skip(self) -> None:
        try:
            state = self._game_stub.SkipTurn(pb.SkipRequest(
                game_id=self.game_id, player_id=self.player_id,
            ))
            self.state_updated.emit(state)
        except grpc.RpcError as e:
            self.action_failed.emit(f"Couldn't skip turn: {e.details()}")
 
    @Slot()
    def request_leave(self) -> None:
        try:
            state = self._game_stub.LeaveGame(pb.LeaveRequest(
                game_id=self.game_id, player_id=self.player_id,
            ))
            self.state_updated.emit(state)
        except grpc.RpcError as e:
            self.action_failed.emit(f"Couldn't leave game: {e.details()}")