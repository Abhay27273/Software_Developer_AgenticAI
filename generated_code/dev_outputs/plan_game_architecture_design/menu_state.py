"""
The state for the main menu.
"""
import pygame
import sys
from states.base_state import State
from states.play_state import PlayState
import config

class MenuState(State):
    """Represents the main menu of the game."""
    def __init__(self, state_machine):
        super().__init__(state_machine)
        self.font = pygame.font.Font(None, 74)
        self.text = self.font.render("Main Menu", True, config.COLOR_WHITE)
        self.text_rect = self.text.get_rect(center=(config.SCREEN_WIDTH / 2, config.SCREEN_HEIGHT / 2 - 50))
        
        self.sub_font = pygame.font.Font(None, 48)
        self.sub_text = self.sub_font.render("Press ENTER to Play", True, config.COLOR_WHITE)
        self.sub_text_rect = self.sub_text.get_rect(center=(config.SCREEN_WIDTH / 2, config.SCREEN_HEIGHT / 2 + 50))

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                self.state_machine.change_state(PlayState(self.state_machine))
            if event.key == pygame.K_ESCAPE:
                pygame.quit()
                sys.exit()

    def update(self, dt: float):
        pass

    def draw(self, screen):
        screen.fill(config.COLOR_BLACK)
        screen.blit(self.text, self.text_rect)
        screen.blit(self.sub_text, self.sub_text_rect)