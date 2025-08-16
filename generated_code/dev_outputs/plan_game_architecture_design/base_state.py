"""
Abstract base class for all game states.
"""
from abc import ABC, abstractmethod

class State(ABC):
    """Abstract base class for a game state."""
    def __init__(self, state_machine):
        self.state_machine = state_machine

    def enter(self):
        """Called when entering the state."""
        pass

    def exit(self):
        """Called when exiting the state."""
        pass

    def pause(self):
        """Called when another state is pushed on top."""
        pass

    def resume(self):
        """Called when the state on top is popped."""
        pass

    @abstractmethod
    def handle_event(self, event):
        """Handle user input and other events."""
        pass

    @abstractmethod
    def update(self, dt: float):
        """Update the state's logic."""
        pass

    @abstractmethod
    def draw(self, screen):
        """Draw the state to the screen."""
        pass