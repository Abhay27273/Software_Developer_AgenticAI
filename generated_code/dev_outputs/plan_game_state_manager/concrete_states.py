from src.game_states.base_state import BaseState
from src.core.scene_manager import SceneManager
from src.game_states.states import GameStateEnum

# Concrete state implementations
class MainMenuState(BaseState):
    def __init__(self, scene_manager: SceneManager):
        super().__init__()
        self.scene_manager = scene_manager

    def enter(self, **kwargs):
        self.logger.info("Entering Main Menu state.")
        self.scene_manager.load_scene("main_menu")

    def exit(self):
        self.logger.info("Exiting Main Menu state.")

    def update(self, dt: float):
        # Handle main menu UI updates, e.g., button animations
        pass

class GameplayState(BaseState):
    def __init__(self, scene_manager: SceneManager):
        super().__init__()
        self.scene_manager = scene_manager

    def enter(self, **kwargs):
        self.logger.info("Entering Gameplay state.")
        level = kwargs.get("level", "level_1") # Example of passing data
        self.scene_manager.load_scene(level)

    def exit(self):
        self.logger.info("Exiting Gameplay state.")

    def update(self, dt: float):
        # Main game loop logic: player movement, physics, AI, etc.
        pass

class PausedState(BaseState):
    def enter(self, **kwargs):
        self.logger.info("Entering Paused state. Game is paused.")
        # In a real game, you might show a pause menu overlay.
        # Time scale would be set to 0.

    def exit(self):
        self.logger.info("Exiting Paused state. Resuming game.")
        # Hide pause menu, set time scale back to 1.

    def update(self, dt: float):
        # Handle pause menu input
        pass

class GameOverState(BaseState):
    def __init__(self, scene_manager: SceneManager):
        super().__init__()
        self.scene_manager = scene_manager

    def enter(self, **kwargs):
        self.logger.info("Entering Game Over state.")
        score = kwargs.get("score", 0)
        self.logger.info(f"Final score: {score}")
        self.scene_manager.load_scene("game_over")

    def exit(self):
        self.logger.info("Exiting Game Over state.")

    def update(self, dt: float):
        # Handle game over screen input (e.g., "Restart" or "Main Menu")
        pass