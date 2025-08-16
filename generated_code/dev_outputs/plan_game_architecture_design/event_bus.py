"""
A simple implementation of the Observer pattern for decoupled communication.
"""
from collections import defaultdict
from utils.logger import logger

class EventBus:
    """A singleton event bus for pub/sub communication."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EventBus, cls).__new__(cls)
            cls._instance.subscribers = defaultdict(list)
            logger.info("EventBus initialized.")
        return cls._instance

    def subscribe(self, event_type: str, callback):
        """Subscribe a callback to an event type."""
        if callback not in self.subscribers[event_type]:
            self.subscribers[event_type].append(callback)
            # logger.debug(f"Subscribed {callback.__name__} to '{event_type}'")

    def unsubscribe(self, event_type: str, callback):
        """Unsubscribe a callback from an event type."""
        try:
            self.subscribers[event_type].remove(callback)
            # logger.debug(f"Unsubscribed {callback.__name__} from '{event_type}'")
        except ValueError:
            logger.warning(f"Attempted to unsubscribe a non-existent callback from '{event_type}'")

    def publish(self, event_type: str, **kwargs):
        """Publish an event to all subscribers."""
        # logger.debug(f"Publishing event '{event_type}' with data: {kwargs}")
        if event_type not in self.subscribers:
            return
        
        # Create a copy to prevent issues if a subscriber modifies the list
        for callback in self.subscribers[event_type][:]:
            callback(**kwargs)

# Singleton instance
event_bus = EventBus()