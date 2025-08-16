import logging
from typing import Dict, Set, Type

from src.core.event_bus import EventBus
from src.core.scene_manager import SceneManager
from src.game_states.base_state import BaseState
from src.game_states.concrete_states import (
    GameOverState,
    GameplayState,
    MainMenuState,
    PausedState,
)
from src.game_states.states import GameStateEnum

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [%(name)s] - %(levelname)s - %(message)s')

class GameStateManager:
    """
    Manages the state of the game, handling transitions and ensuring
    only valid state changes occur.
    """
    def __init__(self, scene_manager: SceneManager, event_bus: EventBus):
        self.logger = logging.getLogger(self.__class__.__name__)
        self._scene_manager = scene_manager
        self._event_bus = event_bus
        
        # Instantiate all possible states, injecting dependencies
        self._states: Dict[GameStateEnum, BaseState] = {
            GameStateEnum.MAIN_MENU: MainMenuState(self._scene_manager),
            GameStateEnum.GAMEPLAY: GameplayState(self._scene_manager),
            GameStateEnum.PAUSED: PausedState(),
            GameStateEnum.GAME_OVER: GameOverState(self._scene_manager),
        }
        
        self.current_state_enum: GameStateEnum = GameStateEnum.NONE
        self.current_state: BaseState | None = None

        # Define the state transition graph
        # Key: current state, Value: set of valid next states
        self._valid_transitions: Dict[GameStateEnum, Set[GameStateEnum]] = {
            GameStateEnum.NONE: {GameStateEnum.MAIN_MENU},
            GameStateEnum.MAIN_MENU: {GameStateEnum.GAMEPLAY},
            GameStateEnum.GAMEPLAY: {GameStateEnum.PAUSED, GameStateEnum.GAME_OVER},
            GameStateEnum.PAUSED: {GameStateEnum.GAMEPLAY, GameStateEnum.MAIN_MENU},
            GameStateEnum.GAME_OVER: {GameStateEnum.MAIN_MENU, GameStateEnum.GAMEPLAY},
        }

    def initialize(self, initial_state: GameStateEnum = GameStateEnum.MAIN_MENU):
        """Initializes the state manager to the first state."""
        self.logger.info(f"Initializing state machine to {initial_state.name}")
        self.change_state(initial_state)

    def change_state(self, new_state_enum: GameStateEnum, **kwargs):
        """
        Requests a transition to a new state. The transition is only performed
        if it is valid according to the transition graph.
        """
        if new_state_enum == self.current_state_enum:
            self.logger.warning(f"Already in state {new_state_enum.name}. Ignoring request.")
            return

        if self._is_valid_transition(new_state_enum):
            self.logger.info(f"Transitioning from {self.current_state_enum.name} to {new_state_enum.name}")
            
            if self.current_state:
                self.current_state.exit()

            previous_state_enum = self.current_state_enum
            self.current_state_enum = new_state_enum
            self.current_state = self._states[new_state_enum]
            
            self.current_state.enter(**kwargs)

            # Publish an event about the state change for other systems to consume
            self._event_bus.publish(
                "gameStateChanged",
                old_state=previous_state_enum,
                new_state=new_state_enum,
                **kwargs
            )
        else:
            self.logger.error(
                f"Invalid state transition requested: "
                f"from {self.current_state_enum.name} to {new_state_enum.name}"
            )

    def _is_valid_transition(self, new_state_enum: GameStateEnum) -> bool:
        """Checks if a transition from the current state to a new one is allowed."""
        if self.current_state_enum not in self._valid_transitions:
            return False
        return new_state_enum in self._valid_transitions[self.current_state_enum]

    def update(self, dt: float):
        """Delegates the update call to the current active state."""
        if self.current_state:
            self.current_state.update(dt)