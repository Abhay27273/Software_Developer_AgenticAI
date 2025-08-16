"""
Manages the high-level game states (e.g., Menu, Playing, Paused).
"""
from utils.logger import logger

class StateMachine:
    """A simple stack-based finite state machine."""
    def __init__(self):
        self.states = []

    def is_empty(self) -> bool:
        return not self.states

    def get_current_state(self):
        return self.states[-1] if not self.is_empty() else None

    def push_state(self, state):
        """Pushes a new state onto the stack."""
        if not self.is_empty():
            self.get_current_state().pause()
        self.states.append(state)
        self.get_current_state().enter()
        logger.info(f"Pushed state: {state.__class__.__name__}")

    def pop_state(self):
        """Pops the current state from the stack."""
        if not self.is_empty():
            self.get_current_state().exit()
            self.states.pop()
            logger.info("Popped state.")
            if not self.is_empty():
                self.get_current_state().resume()

    def change_state(self, state):
        """Changes the current state by popping and then pushing."""
        self.pop_state()
        self.push_state(state)

    def handle_event(self, event):
        if not self.is_empty():
            self.get_current_state().handle_event(event)

    def update(self, dt: float):
        if not self.is_empty():
            self.get_current_state().update(dt)

    def draw(self, screen):
        if not self.is_empty():
            self.get_current_state().draw(screen)