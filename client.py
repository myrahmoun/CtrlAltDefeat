import grpc
import threading
import game_pb2
import game_pb2_grpc

REQUIRED_CATEGORIES = {'Intelligence', 'Technology', 'Governance', 'Cybersecurity'}

# Held by the main thread during interactive prompts to silence the watcher
_my_turn = threading.Lock()


# ── Rendering ─────────────────────────────────────────────────────────────

def render_state(state: game_pb2.GameState) -> None:
    print(f"\n{'='*50}")
    print(f"Game: {state.game_id}  |  Status: {state.status}")
    print("Board positions:")
    for p in state.players:
        marker = " <-- current" if p.id == state.current_player_id else ""
        turn_warning = " (loses next turn)" if p.lose_next_turn else ""
        print(f"  {p.name}: {p.board_position}/19{marker}{turn_warning}")
    if state.winner_id:
        winner = next((p for p in state.players if p.id == state.winner_id), None)
        if winner:
            print(f"\n*** {winner.name} wins! ***")


def show_hand(player: game_pb2.Player) -> None:
    print(f"\n--- {player.name}'s hand ---")
    print("Objectives:")
    for i, c in enumerate(player.hand.objective_cards):
        print(f"  [{i}] {c.name} (R:{c.responsibility}, E:{c.effect})")
    print("Actions:")
    for i, c in enumerate(player.hand.action_cards):
        print(f"  [{i}] {c.name} - {c.category} (R:{c.responsibility}, E:{c.effect})")


# ── Input helpers ─────────────────────────────────────────────────────────

def prompt_card_selection(player: game_pb2.Player):
    """Ask the player to pick 1 objective + 4 action cards. Returns (obj_idx, action_idxs) or None."""
    print("(or type 'back' to cancel)")
    while True:
        try:
            raw = input("\nChoose cards (obj act1 act2 act3 act4 by index): ").strip()
            if raw.lower() == 'back':
                return None
            indices = [int(x) for x in raw.split()]
            if len(indices) != 5:
                print("Need exactly 5 indices.")
                continue

            obj_idx = indices[0]
            action_idxs = indices[1:]

            if obj_idx >= len(player.hand.objective_cards):
                print("Invalid objective index.")
                continue
            if any(i >= len(player.hand.action_cards) for i in action_idxs):
                print("Invalid action index.")
                continue

            selected_categories = {player.hand.action_cards[i].category for i in action_idxs}
            if selected_categories != REQUIRED_CATEGORIES:
                print(f"Need one card from each category: {REQUIRED_CATEGORIES}")
                continue

            return obj_idx, action_idxs

        except ValueError:
            print("Invalid input. Example: 0 0 1 2 3")


def prompt_discard(stub, game_id, player_id, state):
    """Keep prompting the player to discard until hand is <= 6 cards."""
    me = next((p for p in state.players if p.id == player_id), None)
    while me and len(me.hand.action_cards) > 6:
        show_hand(me)
        print(f"\nYou have {len(me.hand.action_cards)} cards — discard down to 6.")
        try:
            idx = int(input("Discard card at index: "))
            state = stub.DiscardCard(game_pb2.DiscardRequest(
                game_id=game_id,
                player_id=player_id,
                card_index=idx,
            ))
            me = next((p for p in state.players if p.id == player_id), None)
        except (ValueError, grpc.RpcError) as e:
            print(f"Error: {e}")
    return state


# ── Background watcher ────────────────────────────────────────────────────

def watch_loop(stub, game_id) -> None:
    """Runs in a background thread — re-renders the board on every server push."""
    try:
        for state in stub.WatchGame(game_pb2.WatchRequest(game_id=game_id)):
            with _my_turn:
                render_state(state)
    except grpc.RpcError:
        pass  # server closed or game ended


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    addr = input("Server address (e.g. 192.168.1.10:50051): ").strip()
    channel = grpc.insecure_channel(addr)
    stub = game_pb2_grpc.BeanBagStub(channel)

    # Lobby: create or join a game
    game_id = input("Game ID to join (or press Enter to create a new game): ").strip()
    if not game_id:
        state = stub.CreateGame(game_pb2.CreateGameRequest())
        game_id = state.game_id
        print(f"Created game: {game_id}  — share this ID with other players")

    while True:
        name = input("Your name: ").strip()
        try:
            join_resp = stub.JoinGame(game_pb2.JoinRequest(game_id=game_id, player_name=name))
            player_id = join_resp.player_id
            print(f"Joined as {name}")
            break
        except grpc.RpcError as e:
            print(f"Couldn't join: {e.details()}")

    # Start background watcher
    t = threading.Thread(target=watch_loop, args=(stub, game_id), daemon=True)
    t.start()

    while True:
        input("\nPress Enter when all players have joined to start the game...")
        try:
            stub.StartGame(game_pb2.StartRequest(game_id=game_id))
            break
        except grpc.RpcError as e:
            print(f"Can't start yet: {e.details()}")

    # Game loop
    while True:
        state = stub.GetState(game_pb2.StateRequest(game_id=game_id))

        if state.status == "finished":
            print("Game over.")
            break

        if state.current_player_id != player_id:
            input("\nWaiting for your turn — press Enter to refresh...")
            continue

        with _my_turn:
            me = next(p for p in state.players if p.id == player_id)
            print(f"\nIt's your turn! (position {me.board_position}/19)")

            if me.lose_next_turn:
                print("You lost your turn!")
                stub.SkipTurn(game_pb2.SkipRequest(game_id=game_id, player_id=player_id))
                continue

            # Draw 2 cards, then force discard if hand exceeds 6
            state = stub.DrawCards(game_pb2.DrawRequest(game_id=game_id, player_id=player_id))
            me = next(p for p in state.players if p.id == player_id)
            if len(me.hand.action_cards) > 6:
                print(f"\nYou drew 2 cards and now have {len(me.hand.action_cards)} — discard down to 6.")
                state = prompt_discard(stub, game_id, player_id, state)
                me = next(p for p in state.players if p.id == player_id)

            selection = None
            action = ''
            while selection is None:
                show_hand(me)
                action = input("\n(p)lay, (s)kip, (d)iscard, or (q)uit? ").strip().lower()

                if action == 'q':
                    stub.LeaveGame(game_pb2.LeaveRequest(game_id=game_id, player_id=player_id))
                    print("You left the game.")
                    return

                if action == 's':
                    stub.SkipTurn(game_pb2.SkipRequest(game_id=game_id, player_id=player_id))
                    break

                if action == 'd':
                    try:
                        idx = int(input("Discard card at index: "))
                        state = stub.DiscardCard(game_pb2.DiscardRequest(
                            game_id=game_id, player_id=player_id, card_index=idx
                        ))
                        me = next(p for p in state.players if p.id == player_id)
                    except (ValueError, grpc.RpcError) as e:
                        print(f"Error: {e}")

                elif action == 'p':
                    selection = prompt_card_selection(me)

        if action != 'p' or selection is None:
            continue

        obj_idx, action_idxs = selection
        try:
            result = stub.PlayTurn(game_pb2.TurnRequest(
                game_id=game_id,
                player_id=player_id,
                objective_index=obj_idx,
                action_indices=action_idxs,
            ))
        except grpc.RpcError as e:
            print(f"Error: {e.details()}")
            continue

        # Print outcome
        if result.lose_turn:
            print(f"Operation failed! R:{result.responsibility} — going offline next turn.")
        elif not result.success:
            print(f"Operation failed. R:{result.responsibility}, E:{result.effect} — no movement.")
        else:
            moved = result.spaces_moved + (1 if result.bonus else 0)
            bonus_str = " (+1 bonus, drew 2 cards)" if result.bonus else ""
            me_updated = next(p for p in result.new_state.players if p.id == player_id)
            print(f"Success! R:{result.responsibility}, E:{result.effect} — moved {moved} space(s){bonus_str}. Now at {me_updated.board_position}.")

        # Discard if bonus draw pushed hand over 6
        prompt_discard(stub, game_id, player_id, result.new_state)

        if result.new_state.status == "finished":
            print("Game over.")
            break

    stub.LeaveGame(game_pb2.LeaveRequest(game_id=game_id, player_id=player_id))


if __name__ == "__main__":
    main()
