"""Test configuration for OpenSearch SOC integration."""
import sys
from pathlib import Path

# Add src to path for imports — conftest is at src/dcc/soc/opensearch/tests/
src_path = Path(__file__).resolve().parents[4]
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))
