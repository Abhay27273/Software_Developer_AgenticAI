"""
The base class for all Components.
"""
class Component:
    """
    Base class for all components. Components are attached to GameObjects
    and primarily hold data, with logic being handled by Systems.
    """
    def __init__(self):
        self.owner = None

    def update(self, dt: float):
        """Update logic for the component (if any)."""
        pass

    def draw(self, screen):
        """Drawing logic for the component (if any)."""
        pass