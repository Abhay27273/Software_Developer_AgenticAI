"""
Handles raw input from Pygame and publishes events to the EventBus.
"""
import pygame
from core.event_bus import event_bus

def handle_event(event):
    """Processes a single Pygame event and publishes it."""
    if event.type == pygame.KEYDOWN:
        event_bus.publish("input", event_type="key", key=event.key, state="down")
    elif event.type == pygame.KEYUP:
        event_bus.publish("input", event_type="key", key=event.key, state="up")