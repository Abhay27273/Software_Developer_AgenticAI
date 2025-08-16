"""
Generates a simple placeholder UV texture map for the car model.

This script creates a 256x256 PNG image with colored regions corresponding
to different parts of the car (body, windows, wheels). This helps verify
the UV mapping of the 3D model in a game engine.

Requires: Pillow library (`pip install Pillow`)
"""
from PIL import Image, ImageDraw

def generate_placeholder_texture(output_path="car_uv_texture.png", size=(256, 256)):
    """
    Creates and saves a placeholder texture image.

    Args:
        output_path (str): The path to save the generated PNG file.
        size (tuple): The (width, height) of the texture.
    """
    try:
        # Create a new image with a light gray background
        img = Image.new('RGB', size, color='lightgray')
        draw = ImageDraw.Draw(img)

        # Define color regions for different car parts
        # These regions would correspond to the UV layout of the model
        regions = {
            "body": {"box": (0, 0, 128, 128), "color": "red", "label": "Body"},
            "windows": {"box": (128, 0, 256, 128), "color": "cyan", "label": "Windows"},
            "wheels": {"box": (0, 128, 128, 256), "color": "black", "label": "Wheels"},
            "details": {"box": (128, 128, 256, 256), "color": "yellow", "label": "Details"}
        }

        # Draw each region
        for key, region in regions.items():
            draw.rectangle(region["box"], fill=region["color"])
            # The text drawing part is optional, but helps in debugging UVs
            # draw.text((region["box"][0] + 5, region["box"][1] + 5), region["label"], fill="white")

        img.save(output_path)
        print(f"✅ Successfully generated placeholder texture at '{output_path}'")

    except Exception as e:
        print(f"❌ Error generating texture: {e}")
        # In a real application, this would be logged to a proper logging service
        raise

if __name__ == "__main__":
    generate_placeholder_texture()