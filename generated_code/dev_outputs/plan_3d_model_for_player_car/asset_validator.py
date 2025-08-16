"""
Validates the car.obj model file to ensure it can be parsed correctly.

This script uses the pywavefront library to load the 3D model. If the file
is corrupted or has an invalid format, the script will raise an error. This
serves as a basic integration test for the 3D asset.

Requires: pywavefront library (`pip install pywavefront`)
"""
import pywavefront
import os

def validate_model(model_path="car.obj"):
    """
    Loads and validates a Wavefront .obj file.

    Args:
        model_path (str): The path to the .obj file.

    Returns:
        bool: True if validation is successful, False otherwise.
    """
    print(f"🔍 Validating model: '{model_path}'...")

    if not os.path.exists(model_path):
        print(f"❌ Error: Model file not found at '{model_path}'")
        return False

    try:
        # Attempt to parse the scene
        scene = pywavefront.Wavefront(model_path, create_materials=True, parse=True)

        # Basic sanity checks
        num_vertices = len(scene.vertices)
        num_faces = sum(len(mesh.faces) for mesh in scene.mesh_list)

        if num_vertices == 0:
            print("❌ Validation Failed: Model contains no vertices.")
            return False
        
        if num_faces == 0:
            print("❌ Validation Failed: Model contains no faces.")
            return False

        print("--- Model Statistics ---")
        print(f"  Vertices: {num_vertices}")
        print(f"  Faces: {num_faces}")
        print(f"  Materials: {list(scene.materials.keys())}")
        print(f"  Meshes: {list(m.name for m in scene.mesh_list)}")
        print("------------------------")
        print("✅ Model validation successful.")
        return True

    except Exception as e:
        print(f"❌ Validation Failed: An error occurred while parsing the model.")
        print(f"   Error: {e}")
        # In a production CI/CD pipeline, this would fail the build
        return False

if __name__ == "__main__":
    is_valid = validate_model()
    # Exit with a non-zero status code on failure for CI/CD integration
    if not is_valid:
        exit(1)