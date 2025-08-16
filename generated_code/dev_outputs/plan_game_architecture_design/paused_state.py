"""
The state for when the game is paused.
"""
import pygame
import sys
from states.base_state import State
import config

class PausedState(State):
    """Represents the paused screen, overlaid on the play state."""
    def __init__(self, state_machine):
        super().__init__(state_machine)
        self.font = pygame.font.Font(None, 100)
        self.text = self.font.render("PAUSED", True, config.COLOR_RED)
        self.text_rect = self.text.get_rect(center=(config.SCREEN_WIDTH / 2, config.SCREEN_HEIGHT / 2))
        
        # Create a semi-transparent overlay
        self.overlay = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT), pygame.SRCALPHA)
        self.overlay.fill((0, 0, 0, 150))

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_p or event.key == pygame.K_ESCAPE:
                self.state_machine.pop_state()

    def update(self, dt: float):
        # The game world does not update while paused.
        pass

    def draw(self, screen):
        # Draw the overlay and the "PAUSED" text
        screen.blit(self.overlay, (0, 0))
        screen.blit(self.text, self.text_rect)