"""
Unit tests for the core EventBus.
"""
import unittest
from unittest.mock import Mock
from core.event_bus import EventBus

class TestEventBus(unittest.TestCase):

    def setUp(self):
        # Reset the singleton for each test to ensure isolation
        EventBus._instance = None
        self.event_bus = EventBus()

    def test_singleton_instance(self):
        """Test that EventBus is a singleton."""
        eb2 = EventBus()
        self.assertIs(self.event_bus, eb2)

    def test_subscribe_and_publish(self):
        """Test basic subscription and event publishing."""
        mock_callback = Mock()
        self.event_bus.subscribe("test_event", mock_callback)
        self.event_bus.publish("test_event", data="hello")
        
        mock_callback.assert_called_once_with(data="hello")

    def test_publish_to_unsubscribed_event(self):
        """Test that publishing to an event with no subscribers does not error."""
        mock_callback = Mock()
        try:
            self.event_bus.publish("non_existent_event", data="test")
        except Exception as e:
            self.fail(f"Publishing to an unsubscribed event raised an exception: {e}")
        mock_callback.assert_not_called()

    def test_unsubscribe(self):
        """Test that unsubscribing a callback works correctly."""
        mock_callback = Mock()
        self.event_bus.subscribe("test_event", mock_callback)
        self.event_bus.unsubscribe("test_event", mock_callback)
        self.event_bus.publish("test_event", data="hello")
        
        mock_callback.assert_not_called()

    def test_multiple_subscribers(self):
        """Test that multiple subscribers for the same event are all called."""
        mock_callback1 = Mock()
        mock_callback2 = Mock()
        
        self.event_bus.subscribe("multi_event", mock_callback1)
        self.event_bus.subscribe("multi_event", mock_callback2)
        
        self.event_bus.publish("multi_event", value=123)
        
        mock_callback1.assert_called_once_with(value=123)
        mock_callback2.assert_called_once_with(value=123)

if __name__ == '__main__':
    unittest.main()