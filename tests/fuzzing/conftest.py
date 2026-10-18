"""Pytest configuration for fuzzing tests."""
import sys
from pathlib import Path

# Add src to path for imports
src_path = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(src_path))
