"""
Pytest configuration file for test setup.

This file ensures that the project root is added to sys.path so that
local packages (like 'handlers', 'lambda', 'utils', etc.) are importable
in tests without installation.
"""
import sys
from pathlib import Path

# Add repo root to sys.path so local packages are importable
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Optional: Add lambda directory if it exists (for lambda function imports)
LAMBDA_DIR = REPO_ROOT / "lambda"
if LAMBDA_DIR.exists() and str(LAMBDA_DIR) not in sys.path:
    sys.path.insert(0, str(LAMBDA_DIR))
