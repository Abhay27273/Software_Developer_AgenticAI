"""
Manages the active scenes in the game.
"""
from utils.logger import logger

class SceneManager:
    """Handles loading, unloading, and transitioning between scenes."""
    def __init__(self):
        self.current_scene = None

    def set_scene(self, scene):
        if self.current_scene:
            self.current_scene.unload()
        
        self.current_scene = scene
        if self.current_scene:
            self.current_scene.load()
            logger.info(f"Scene set to: {scene.__class__.__name__}")

    def get_current_scene(self):
        return self.current_scene