"""
Main entry point for the game. Initializes the engine and runs the game loop.
"""
import pygame
import sys
import config
from utils.logger import logger
from core.state_machine import StateMachine
from states.menu_state import MenuState

class Game:
    """The main game class."""
    def __init__(self):
        pygame.init()
        logger.info("Pygame initialized.")
        
        self.screen = pygame.display.set_mode((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
        pygame.display.set_caption(config.WINDOW_TITLE)
        
        self.clock = pygame.time.Clock()
        self.is_running = True
        
        self.state_machine = StateMachine()
        logger.info("Game components initialized.")

    def run(self):
        """Starts the main game loop."""
        self.state_machine.push_state(MenuState(self.state_machine))
        logger.info("Starting game loop.")
        
        while self.is_running:
            # Delta time in seconds
            dt = self.clock.tick(config.FPS) / 1000.0
            
            self._handle_events()
            self._update(dt)
            self._draw()
            
        self._cleanup()

    def _handle_events(self):
        """Process all pending events from Pygame."""
        # A special case for the QUIT event to ensure the game can always close.
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.is_running = False
            else:
                # Delegate event handling to the current state
                self.state_machine.handle_event(event)

    def _update(self, dt: float):
        """Update the game logic."""
        self.state_machine.update(dt)

    def _draw(self):
        """Render the game to the screen."""
        # The active state is responsible for drawing
        current_state = self.state_machine.get_current_state()
        if current_state:
            # The state might have its own background drawing logic
            # before drawing scene objects.
            current_state.draw(self.screen)
        
        pygame.display.flip()

    def _cleanup(self):
        """Clean up resources before exiting."""
        logger.info("Cleaning up and shutting down.")
        pygame.quit()
        sys.exit()

if __name__ == "__main__":
    try:
        game = Game()
        game.run()
    except Exception as e:
        logger.error(f"An unhandled exception occurred: {e}", exc_info=True)
        pygame.quit()
        sys.exit()