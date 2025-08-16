"""
Handles drawing all renderable objects to the screen.
"""
from components.sprite_renderer import SpriteRendererComponent

def draw(game_objects: list, screen):
    """
    Iterates through all game objects and calls the draw method
    of their renderer component.
    """
    for go in game_objects:
        if go.has_component(SpriteRendererComponent):
            renderer = go.get_component(SpriteRendererComponent)
            renderer.draw(screen)