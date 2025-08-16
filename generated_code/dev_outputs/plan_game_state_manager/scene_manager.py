import logging

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [SceneManager] - %(message)s')

class SceneManager:
    """
    Manages loading, unloading, and switching between game scenes.
    This is a stub implementation based on the expected output of task_004.
    """
    def __init__(self):
        self.current_scene: str | None = None

    def load_scene(self, scene_name: str):
        """
        Loads a new scene. In a real implementation, this would involve
        loading assets, creating game objects, etc.
        """
        if self.current_scene == scene_name:
            logging.warning(f"Scene '{scene_name}' is already loaded.")
            return

        logging.info(f"Unloading scene: {self.current_scene}")
        # Unload resources for the old scene here
        
        logging.info(f"Loading scene: {scene_name}...")
        self.current_scene = scene_name
        # Load assets and initialize the new scene here
        logging.info(f"Scene '{scene_name}' loaded successfully.")