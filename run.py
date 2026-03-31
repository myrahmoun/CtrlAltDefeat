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
    while True:
        try:
            raw = input("\nChoose cards (obj act1 act2 act3 act4 by index): ")
            indices = [int(x) for x in raw.strip().split()]
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


def register_players(game):
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
            game.execute_turn(player, None, []) # TODO: Will cause bugs in the future
        else:
            show_hand(player)
            action = input("\n(p)lay or (s)kip? ").strip().lower()
            if action == 's':
                game.pass_turn()
                continue
            obj, actions = prompt_card_selection(player)
            print(f"\nPlaying: {obj.name} + {[c.name for c in actions]}")
            game.execute_turn(player, obj, actions)

        if game.winner:
            print(f"\n{'='*50}")
            print(f"{game.winner.name} wins! (position {game.winner.boardPosition})")
            break

        input("\nPress Enter for next turn...")

    print("Game over.")


if __name__ == "__main__":
    main()
