# config.py
from pathlib import Path

# Use the /tmp directory, which is guaranteed to be writable
GENERATED_CODE_ROOT = Path("/tmp/generated_code")

# DEV_OUTPUT_DIR will then be a subdirectory of /tmp/generated_code
DEV_OUTPUT_DIR = GENERATED_CODE_ROOT / "dev_outputs"

# Add other configurations here, like model names
DEFAULT_MODEL_NAME = "gemini-2.5-pro"
PLANNER_MODEL_NAME = "gemini-2.5-pro"