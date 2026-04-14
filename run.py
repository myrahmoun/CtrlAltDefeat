from refactor import Game, GameStats
from player import Player


REQUIRED_CATEGORIES = {'Intelligence', 'Technology', 'Governance', 'Cybersecurity'}


def show_hand(player):
    print(f"\n--- {player.name}'s hand ---")
    print("Objectives:")
    for i, c in enumerate(player.hand.objective_cards):
        print(f"  [{i}] {c.name} (R:{c.responsibility}, E:{c.effect})")
    print("Actions:")
    for i, c in enumerate(player.hand.action_cards):
        print(f"  [{i}] {c.name} - {c.category} (R:{c.responsibility}, E:{c.effect})")


def prompt_card_selection(player):
    print("(or type 'back' to go back)")
    while True:
        try:
            raw = input("\nChoose cards (obj act1 act2 act3 act4 by index): ").strip()
            if raw.lower() == 'back':
                return None, None
            indices = [int(x) for x in raw.split()]
            if len(indices) != 5:
                print("Need exactly 5 indices.")
                continue

            obj = player.hand.objective_cards[indices[0]]
            actions = [player.hand.action_cards[i] for i in indices[1:]]

            if {c.category for c in actions} != REQUIRED_CATEGORIES:
                print(f"Need one of each: {REQUIRED_CATEGORIES}")
                continue

            return obj, actions

        except (ValueError, IndexError):
            print("Invalid input. Example: 0 0 1 2 3")


def register_players(game: Game):
    while True:
        try:
            n = int(input("How many players (3-6)? "))
            if 3 <= n <= 6:
                break
            print("Must be between 3 and 6.")
        except ValueError:
            print("Enter a number.")

    for i in range(n):
        name = input(f"Player {i+1} name: ")
        game.players.append(Player(name))

    game.setup_game()

    print("\nTurn order:")
    for i, p in enumerate(game.turn_order):
        print(f"  {i+1}. {p.name}")


def main():
    game = Game("game-1")
    register_players(game)

    turn = 0
    while game.status == GameStats.PLAYING:
        turn += 1
        player = game.get_current_player()

        print(f"\n{'='*50}")
        print(f"Turn {turn} — {player.name} (position {player.boardPosition}/19)")
        print(game.board.get_visual_board(game.players))

        if player.lose_next_turn:
            print(f"{player.name} lost their turn!")
            game.execute_turn(player, None, [])
        else:
            # Draw 2 cards at start of turn
            for _ in range(2):
                game._refill_if_empty(game.action_pile)
                card = game.action_pile.draw()
                if card:
                    player.hand.action_cards.append(card)

            # Enforce 6-card max before player decides
            while len(player.hand.action_cards) > 6:
                show_hand(player)
                print(f"\nYou have {len(player.hand.action_cards)} cards — discard down to 6.")
                try:
                    idx = int(input("Discard card at index: "))
                    card = player.hand.action_cards[idx]
                    player.hand.action_cards.remove(card)
                    game.discard_pile.add(card)
                except (ValueError, IndexError):
                    print("Invalid index.")

            show_hand(player)
            action = input("\n(p)lay or (s)kip? ").strip().lower()
            if action == 's':
                game.pass_turn()
            else:
                obj, actions = prompt_card_selection(player)
                if obj is None or actions is None:
                    game.pass_turn()
                    continue
                print(f"\nPlaying: {obj.name} + {[c.name for c in actions]}")
                result = game.execute_turn(player, obj, actions)
                if result:
                    r, e = result['responsibility'], result['effect']
                    if result['lose_turn']:
                        print(f"Operation failed! R:{r} — going offline next turn.")
                    elif not result['success']:
                        print(f"Operation failed. R:{r}, E:{e} — no movement.")
                    else:
                        moved = result['spaces_moved'] + (1 if result['bonus'] else 0)
                        bonus_str = " (+1 bonus, drew 2 cards)" if result['bonus'] else ""
                        print(f"Success! R:{r}, E:{e} — moved {moved} space(s){bonus_str}. Now at {player.boardPosition}.")

            # Enforce 6-card max after bonus draw
            while len(player.hand.action_cards) > 6:
                show_hand(player)
                print(f"\nYou have {len(player.hand.action_cards)} cards — discard down to 6.")
                try:
                    idx = int(input("Discard card at index: "))
                    card = player.hand.action_cards[idx]
                    player.hand.action_cards.remove(card)
                    game.discard_pile.add(card)
                except (ValueError, IndexError):
                    print("Invalid index.")

        if game.winner:
            print(f"\n{'='*50}")
            print(f"{game.winner.name} wins! (position {game.winner.boardPosition})")
            break

        input("\nPress Enter for next turn...")

    print("Game over.")


if __name__ == "__main__":
    main()
