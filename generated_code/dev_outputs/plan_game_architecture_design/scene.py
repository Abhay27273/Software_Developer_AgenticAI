"""
Base class for a game scene.
"""
class Scene:
    """Represents a single screen or level in the game."""
    def __init__(self):
        self.game_objects = []

    def add_game_object(self, game_object):
        self.game_objects.append(game_object)

    def remove_game_object(self, game_object):
        self.game_objects.remove(game_object)

    def load(self):
        """Called when the scene is loaded."""
        pass

    def unload(self):
        """Called when the scene is unloaded."""
        pass

    def update(self, dt: float):
        """Update all game objects in the scene."""
        for go in self.game_objects:
            go.update(dt)

    def draw(self, screen):
        """Draw all game objects in the scene."""
        for go in self.game_objects:
            go.draw(screen)