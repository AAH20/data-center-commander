"""
Pytest configuration for Data Center Commander compliance tests.
"""

import os
import sys

# Add the project root to the Python path
project_root = os.path.join(os.path.dirname(__file__), "..", "..")
sys.path.insert(0, project_root)

# Note: We intentionally do NOT add policies/ to sys.path because
# policies/checkov/ has an __init__.py that would shadow the installed
# checkov package. The checkov test file loads policy modules directly
# using importlib.util.spec_from_file_location instead.
