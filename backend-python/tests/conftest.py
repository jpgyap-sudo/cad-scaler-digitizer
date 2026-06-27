"""pytest configuration — ensures app module is importable from tests."""
import sys
from pathlib import Path

# test_templates.py and other test files import from app.*.
# When running via pytest, the cwd is tests/ and app/ isn't on sys.path.
# This conftest adds backend-python/ to sys.path so imports resolve correctly.
BACKEND_DIR = Path(__file__).resolve().parent  # backend-python/tests/
PROJECT_DIR = BACKEND_DIR.parent               # backend-python/
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))
