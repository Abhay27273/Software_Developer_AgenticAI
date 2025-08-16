"""
The main gameplay scene, containing the player and other game elements.
"""
from core.scene import Scene
from core.game_object import GameObject
from components.transform import TransformComponent
from components.sprite_renderer import SpriteRendererComponent
from components.physics_body import PhysicsBodyComponent
from components.player_controller import PlayerControllerComponent
import config

class PlayScene(Scene):
    """The scene for the main gameplay."""
    def load(self):
        super().load()
        self.create_player()

    def create_player(self):
        """Creates the player game object and adds it to the scene."""
        player = GameObject("Player")
        
        # Add components
        player.add_component(TransformComponent(
            x=(config.SCREEN_WIDTH - config.PLAYER_SIZE) / 2,
            y=(config.SCREEN_HEIGHT - config.PLAYER_SIZE) / 2,
            w=config.PLAYER_SIZE,
            h=config.PLAYER_SIZE
        ))
        player.add_component(SpriteRendererComponent(config.COLOR_WHITE))
        player.add_component(PhysicsBodyComponent())
        player.add_component(PlayerControllerComponent())
        
        self.add_game_object(player)