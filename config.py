# config.py
from pathlib import Path
import os

# Use the current working directory's generated_code folder for Windows compatibility
# This will create the generated_code folder in your project directory
GENERATED_CODE_ROOT = Path.cwd() / "generated_code"

# DEV_OUTPUT_DIR will then be a subdirectory of generated_code in your project
DEV_OUTPUT_DIR = GENERATED_CODE_ROOT / "dev_outputs"

# Add other configurations here, like model names
DEFAULT_MODEL_NAME = "gemini-2.5-pro"
PLANNER_MODEL_NAME = "gemini-2.5-pro"