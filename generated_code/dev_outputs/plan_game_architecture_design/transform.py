"""
Component for position, rotation, and scale.
"""
import pygame
from core.component import Component

class TransformComponent(Component):
    def __init__(self, x: float, y: float, w: int, h: int):
        super().__init__()
        self.position = pygame.Vector2(x, y)
        self.width = w
        self.height = h