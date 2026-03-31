In turn_manager:

We don't really need a TurnManager.__init__() function. The only thing it's referring to is the game object so that it can access it. Just move turn execution to game.

## execute_turn()
- no need for the lose_turn() check to include adding to log and checking if flag exists. If lost_turn, next_turn. Then reset flag.
- checking if enough action cards should be an assertion?
- remove card display on board for now.
- add cleanup function to discard action cards, and objective
- remove logging and UI


# USE from pydantic import BaseModel, ConfigDict, EmailStr, StrictInt, ValidationError ????
