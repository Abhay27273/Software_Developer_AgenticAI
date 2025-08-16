"""
Component for basic physics properties like velocity.
"""
import pygame
from core.component import Component

class PhysicsBodyComponent(Component):
    def __init__(self):
        super().__init__()
        self.velocity = pygame.Vector2(0, 0)