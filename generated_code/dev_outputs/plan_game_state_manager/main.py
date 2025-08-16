import time
import logging
from src.core.event_bus import EventBus
from src.core.scene_manager import SceneManager
from src.game_states.state_manager import GameStateManager
from src.game_states.states import GameStateEnum

# --- Setup Logging ---
# The logger is configured in the modules, but we can set a root level here.
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [%(name)s] - %(levelname)s - %(message)s')
log = logging.getLogger("Main")

# --- Analytics System (Example of an event subscriber) ---
def on_game_state_changed(old_state, new_state, **kwargs):
    """A simple subscriber that logs state changes, simulating an analytics service."""
    log.info(f"[AnalyticsService] Detected state change from {old_state.name} to {new_state.name}")
    if 'score' in kwargs:
        log.info(f"[AnalyticsService] Final score received: {kwargs['score']}")

def main():
    """Main function to demonstrate the Game State Manager."""
    log.info("--- Initializing Game Systems ---")
    scene_manager = SceneManager()
    event_bus = EventBus()
    
    # Subscribe our analytics service to the state change event
    event_bus.subscribe("gameStateChanged", on_game_state_changed)
    
    state_manager = GameStateManager(scene_manager, event_bus)

    log.info("\n--- Starting Game Simulation ---")
    
    # 1. Initialize the game
    state_manager.initialize()
    time.sleep(0.1)

    # 2. Try an invalid transition
    log.info("\n>>> Attempting INVALID transition: MAIN_MENU -> PAUSED")
    state_manager.change_state(GameStateEnum.PAUSED)
    log.info(f"Current state is still: {state_manager.current_state_enum.name}")
    time.sleep(0.1)

    # 3. Start the game
    log.info("\n>>> Attempting VALID transition: MAIN_MENU -> GAMEPLAY")
    state_manager.change_state(GameStateEnum.GAMEPLAY, level="forest_level")
    time.sleep(0.1)

    # 4. Pause the game
    log.info("\n>>> Attempting VALID transition: GAMEPLAY -> PAUSED")
    state_manager.change_state(GameStateEnum.PAUSED)
    time.sleep(0.1)

    # 5. Resume the game
    log.info("\n>>> Attempting VALID transition: PAUSED -> GAMEPLAY")
    state_manager.change_state(GameStateEnum.GAMEPLAY)
    time.sleep(0.1)

    # 6. Game over
    log.info("\n>>> Attempting VALID transition: GAMEPLAY -> GAME_OVER")
    state_manager.change_state(GameStateEnum.GAME_OVER, score=9500)
    time.sleep(0.1)

    # 7. Return to menu
    log.info("\n>>> Attempting VALID transition: GAME_OVER -> MAIN_MENU")
    state_manager.change_state(GameStateEnum.MAIN_MENU)
    
    log.info("\n--- Game Simulation Finished ---")


if __name__ == "__main__":
    main()