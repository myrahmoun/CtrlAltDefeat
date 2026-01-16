# turn_manager.py

from typing import List, Dict, Tuple, Optional
from player import Player
from cards import ObjectiveCard, ActionCard, GlitchCard
from operation import Operation, LoseTurnException, InvalidOperationException


class TurnManager:
    """
    Controls turn sequence and executes turn logic.
    Works with Game's objects but doesn't own them.
    """

    def __init__(self, game) -> None:
        """
        Args:
            game: Reference to parent Game object
        """
        self.game = game
        self.turn_history: List[dict] = []  # Optional: log of past turns

    def execute_turn(self, player: Player, objective: ObjectiveCard, actions: List[ActionCard]) -> None:
        """
        Execute a complete turn for a player.
        
        Args:
            player: The player taking their turn
            objective: The objective card being played
            actions: List of 4 action cards (one per category)
            die_roll: Optional die roll value (required if operation needs die roll)
            
        Returns:
            dict with turn results including success, spaces_moved, etc.
        """
        # Check if player has lost rights to this turn
        if player.lose_next_turn:
            player.lose_next_turn = False
            self.skip_turn(player, reason = "lost_previous_turn")
            return

        # Check that we have four action cards and an objective card
        if len(actions) != 4:
            raise ValueError(f"Need exactly 4 action cards, got {len(actions)}")
        if not objective:
            raise ValueError("Need one objective card, got none")
    

        # Display cards on board
        self.game.board.display_cards(objective, actions)

        # Build an operation
        operation = Operation(objective)
        for action in actions:
            operation.add_action(action)
        
        try:
            # Evaluate operation. Might raise LoseTurnException
            spaces_to_move = operation.evaluate_op()
            success = True

            # Move Player
            old_pos = player.boardPosition
            new_pos = min(old_pos + spaces_to_move , 19) # Cap position at 19
            player.boardPosition = new_pos

            # Bonus (if applicable): extra space + draw two action cards
            bonus_applied = False
            if operation.responsibility >= 4:
                # Move an extra space
                new_pos = min(new_pos + 1, 19)
                player.boardPosition = new_pos
                bonus_applied = True

                # Draw 2 extra cards
                for _ in range(2):
                    self.game.refill_deck_if_empty(self.game.action_pile)
                    card = self.game.action_pile.draw()
                    if card and len(player.hand.action_cards) < 6:  # Respect 6 card limit
                        player.hand.action_cards.append(card)
                    else:
                        raise RuntimeError("Adding bonus card failed")

        except LoseTurnException:
            player.lose_next_turn = True # Set flag for next turn
            success = False
            spaces_to_move = 0        

        # Check if current_player won
        if player.boardPosition >= 19:
            self.game.end_game(player)
            return

        # Discard action cards
        for card in actions:
            self.game.discard_pile.add(card)
            player.hand.action_cards.remove(card)

        # Return objective card to the bottom of the objective deck
        player.hand.objective_cards.remove(objective)
        self.game.objective_pile.content.append(objective)
        
        # Draw replacement cards
        # Objective
        new_obj = self.game.objective_pile.draw()
        if not new_obj:
            raise RuntimeError("Cannot draw objective card")
        player.hand.objective_cards.append(new_obj)

        # Action - temporarily simplified for demo purposes
        actions_to_draw = min(4, 6 - len(player.hand.action_cards))
        for _ in range(actions_to_draw):
            self.game.refill_deck_if_empty(self.game.action_pile)
            card = self.game.action_pile.draw()
            if not card:
                raise RuntimeError("Cannot draw action card")
            player.hand.action_cards.append(card)


        # Clear board (UI)
        self.game.board.clear_card_slots()

        # Log turn
        self.turn_history.append({
            'event': 'turn_executed',
            'player_id': player.id,
            'player_name': player.name,
            'success': success,
            'spaces_moved': spaces_to_move,
            'final_position': player.boardPosition
        })

        # Move to next turn
        self.game.next_turn()

        # Can return a dict of results here (later for gRPC)

    def skip_turn(self, player: Player, reason: str = "timeout") -> None:
        """
        Skip a player's turn (e.g., due to timeout or glitch effect).
        """
        self.turn_history.append({
            'event': 'turn_skipped',
            'player_id': player.id,
            'player_name': player.name,
            'reason': reason
        })
        
        # Move to next turn
        self.game.next_turn()


    def pass_turn(self, player: Player) -> None:
        """Player voluntarily passes their turn."""
        self.skip_turn(player, reason="passed")