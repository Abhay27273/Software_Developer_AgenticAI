from abc import ABC, abstractmethod
import logging

class BaseState(ABC):
    """
    Abstract base class for all game states.
    It defines the common interface for state operations.
    """
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def enter(self, **kwargs):
        """
        Called once when the state machine transitions into this state.
        Used for setup, resource loading, and UI initialization.
        """
        pass

    @abstractmethod
    def exit(self):
        """
        Called once when the state machine transitions out of this state.
        Used for cleanup, resource unloading, and saving data.
        """
        pass

    @abstractmethod
    def update(self, dt: float):
        """
        Called every frame while this state is active.
        `dt` is the delta time since the last frame.
        """
        pass