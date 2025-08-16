"""
The base class for any object in the game world.
"""
import uuid

class GameObject:
    """A container for components that represents an object in the game."""
    def __init__(self, name: str = "GameObject"):
        self.id = uuid.uuid4()
        self.name = name
        self._components = {}

    def add_component(self, component):
        """Adds a component to the game object."""
        component.owner = self
        component_type = type(component)
        self._components[component_type] = component
        return component

    def get_component(self, component_type):
        """Retrieves a component of a specific type."""
        return self._components.get(component_type)

    def has_component(self, component_type) -> bool:
        """Checks if the game object has a component of a specific type."""
        return component_type in self._components

    def update(self, dt: float):
        """Update all components."""
        for component in self._components.values():
            component.update(dt)

    def draw(self, screen):
        """Draw all drawable components."""
        for component in self._components.values():
            component.draw(screen)