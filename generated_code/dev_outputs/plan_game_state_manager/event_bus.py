import logging
from typing import Any, Callable, Dict, List

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [EventBus] - %(message)s')

class EventBus:
    """
    A simple event bus for decoupled communication between game systems.
    This is a stub implementation based on the expected output of task_007.
    """
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}

    def subscribe(self, event_type: str, callback: Callable):
        """Subscribe a callback to an event type."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)
        logging.info(f"New subscription to event '{event_type}' by {callback.__name__}")

    def publish(self, event_type: str, *args: Any, **kwargs: Any):
        """Publish an event to all subscribers."""
        if event_type in self._subscribers:
            logging.info(f"Publishing event '{event_type}' with args: {args}, kwargs: {kwargs}")
            for callback in self._subscribers[event_type]:
                try:
                    callback(*args, **kwargs)
                except Exception as e:
                    logging.error(f"Error in event handler for '{event_type}': {e}")