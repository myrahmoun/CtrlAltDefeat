# tests/test_cardpile.py
import pytest
from cardpile import CardPile
from cards import ActionCard, ObjectiveCard, GlitchCard


class TestCardPile:
    
    def test_inxit_creates_empty_pile(self):
        pile = CardPile('action')
        assert pile.type == 'action'
        assert pile.is_empty()
        assert pile.size() == 0
    
    def test_add_card_to_pile(self):
        pile = CardPile('action')
        card = ActionCard("Test", "Description", "Intelligence", 5, 3)
        
        pile.add(card)
        
        assert pile.size() == 1
        assert not pile.is_empty()
        assert card.cardStatus == "in_action_pile"
    
    def test_draw_from_empty_pile_returns_none(self):
        pile = CardPile('objective')
        assert pile.draw() is None
    
    def test_draw_removes_card_from_pile(self):
        pile = CardPile('action')
        card1 = ActionCard("Card1", "Desc", "Technology", 4, 2)
        card2 = ActionCard("Card2", "Desc", "Governance", 6, 4)
        pile.add(card1)
        pile.add(card2)
        
        drawn = pile.draw()
        
        assert drawn == card1  # FIFO - first added, first drawn
        assert pile.size() == 1
        assert pile.content[0] == card2
    
    def test_load_cards_sets_status(self):
        pile = CardPile('discard')
        cards = [
            ActionCard("C1", "D", "Intelligence", 3, 2),
            ActionCard("C2", "D", "Technology", 5, 3)
        ]
        
        pile.load_cards(cards)
        
        assert pile.size() == 2
        for card in cards:
            assert card.cardStatus == "in_discard_pile"
    
    def test_multiple_draw_empties_pile(self):
        pile = CardPile('action')
        pile.add(ActionCard("C1", "D", "Intelligence", 3, 2))
        pile.add(ActionCard("C2", "D", "Technology", 5, 3))
        
        pile.draw()
        pile.draw()
        
        assert pile.is_empty()
        assert pile.draw() is None
    
    def test_repr_shows_type_and_size(self):
        pile = CardPile('objective')
        pile.add(ObjectiveCard("Obj1", "Desc", 10, 5))
        
        repr_str = repr(pile)
        
        assert "objective" in repr_str
        assert "1" in repr_str