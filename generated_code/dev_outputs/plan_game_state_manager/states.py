from enum import Enum, auto

class GameStateEnum(Enum):
    """Enumeration of all possible game states."""
    NONE = auto()
    MAIN_MENU = auto()
    GAMEPLAY = auto()
    PAUSED = auto()
    GAME_OVER = auto()