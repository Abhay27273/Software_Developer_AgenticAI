"""
Updates the position of objects based on their velocity.
"""
from components.transform import TransformComponent
from components.physics_body import PhysicsBodyComponent

def update(game_objects: list, dt: float):
    """
    Iterates through all game objects and updates their position
    based on their physics properties.
    """
    for go in game_objects:
        if go.has_component(TransformComponent) and go.has_component(PhysicsBodyComponent):
            transform = go.get_component(TransformComponent)
            physics = go.get_component(PhysicsBodyComponent)
            
            transform.position += physics.velocity * dt