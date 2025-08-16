"""
Component that handles player input to control a GameObject.
"""
import pygame
from core.component import Component
from core.event_bus import event_bus
from components.physics_body import PhysicsBodyComponent
import config

class PlayerControllerComponent(Component):
    def __init__(self):
        super().__init__()
        self.move_input = pygame.Vector2(0, 0)
        event_bus.subscribe("input", self.on_input)

    def on_input(self, event_type, key, state):
        """Callback for input events."""
        if event_type != "key":
            return
            
        # Update move_input vector based on key presses
        if key == pygame.K_UP:
            self.move_input.y = -1 if state == "down" else 0
        elif key == pygame.K_DOWN:
            self.move_input.y = 1 if state == "down" else 0
        elif key == pygame.K_LEFT:
            self.move_input.x = -1 if state == "down" else 0
        elif key == pygame.K_RIGHT:
            self.move_input.x = 1 if state == "down" else 0

    def update(self, dt: float):
        physics_body = self.owner.get_component(PhysicsBodyComponent)
        if physics_body:
            if self.move_input.length() > 0:
                # Normalize to prevent faster diagonal movement
                physics_body.velocity = self.move_input.normalize() * config.PLAYER_SPEED
            else:
                physics_body.velocity = pygame.Vector2(0, 0)
    
    def __del__(self):
        # Important to unsubscribe to prevent memory leaks
        event_bus.unsubscribe("input", self.on_input)