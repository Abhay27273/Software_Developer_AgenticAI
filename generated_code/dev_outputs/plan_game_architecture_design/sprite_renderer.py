"""
Component for rendering a sprite or a simple shape.
"""
import pygame
from core.component import Component
from components.transform import TransformComponent

class SpriteRendererComponent(Component):
    def __init__(self, color):
        super().__init__()
        self.color = color

    def draw(self, screen):
        transform = self.owner.get_component(TransformComponent)
        if transform:
            rect = pygame.Rect(transform.position.x, transform.position.y, transform.width, transform.height)
            pygame.draw.rect(screen, self.color, rect)