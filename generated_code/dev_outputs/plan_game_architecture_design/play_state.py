"""
The main gameplay state.
"""
import pygame
from states.base_state import State
from states.paused_state import PausedState
from scenes.play_scene import PlayScene
from systems import input_system, physics_system, render_system
import config

class PlayState(State):
    """Represents the active gameplay state."""
    def __init__(self, state_machine):
        super().__init__(state_machine)
        self.scene = PlayScene()
        self.is_paused = False

    def enter(self):
        self.scene.load()

    def exit(self):
        self.scene.unload()

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_p:
                self.state_machine.push_state(PausedState(self.state_machine))
            if event.key == pygame.K_ESCAPE:
                # In a real game, you might push an EndState or go back to Menu
                from states.menu_state import MenuState
                self.state_machine.change_state(MenuState(self.state_machine))
        
        # Delegate other events to the input system
        input_system.handle_event(event)

    def update(self, dt: float):
        # In a more complex game, you might have an update_system
        # that orchestrates other systems.
        physics_system.update(self.scene.game_objects, dt)

    def draw(self, screen):
        screen.fill(config.COLOR_BLUE)
        render_system.draw(self.scene.game_objects, screen)