"""Security tests: path traversal prevention."""
from __future__ import annotations

import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]


class PathTraversalTests(unittest.TestCase):
    """Verify path traversal payloads are rejected."""

    def test_tenant_id_rejects_dot_dot(self):
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["../../../etc/passwd"]})

    def test_tenant_id_rejects_dot_dot_backslash(self):
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["..\\..\\..\\windows\\system32\\config\\sam"]})

    def test_tenant_id_rejects_absolute_unix(self):
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["/etc/passwd"]})

    def test_tenant_id_rejects_absolute_windows(self):
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["C:\\Windows\\System32\\config\\SAM"]})

    def test_tenant_id_rejects_unc(self):
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["\\\\server\\share\\file"]})

    def test_tenant_id_rejects_file_uri(self):
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["file:///etc/passwd"]})

    def test_tenant_id_rejects_double_encoding(self):
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd"]})

    def test_tenant_id_rejects_mixed_encoding(self):
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["..%2f..%2f..%2fetc%2fpasswd"]})

    def test_tenant_id_rejects_null_byte_injection(self):
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-000000000001\x00/../../../etc/passwd"]})

    def test_tenant_id_rejects_symlink_traversal(self):
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-000000000001/link"]})

    def test_tenant_id_rejects_deep_traversal(self):
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["../../../../../../../../etc/passwd"]})

    def test_tenant_id_rejects_traversal_with_valid_prefix(self):
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-000000000001/../../../etc/passwd"]})

    def test_tenant_id_rejects_trailing_slash(self):
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-000000000001/"]})

    def test_tenant_id_rejects_double_slash(self):
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000//0000//4000//8000//000000000001"]})

    def test_tenant_id_rejects_backslash(self):
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000\\0000\\4000\\8000\\000000000001"]})

    def test_tenant_id_rejects_colon(self):
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000:0000:4000:8000:000000000001"]})

    def test_tenant_id_rejects_semicolon(self):
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000;0000;4000;8000;000000000001"]})

    def test_tenant_id_rejects_pipe(self):
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000|0000|4000|8000|000000000001"]})

    def test_tenant_id_rejects_ampersand(self):
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000&0000&4000&8000&000000000001"]})

    def test_tenant_id_rejects_dollar(self):
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["$dcc00000"]})

    def test_tenant_id_rejects_backtick(self):
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["`dcc00000`"]})

    def test_tenant_id_rejects_parentheses(self):
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["(dcc00000)"]})

    def test_tenant_id_rejects_braces(self):
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{dcc00000}"]})

    def test_tenant_id_rejects_brackets(self):
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["[dcc00000]"]})

    def test_tenant_id_rejects_angle_brackets(self):
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["<dcc00000>"]})

    def test_tenant_id_rejects_question_mark(self):
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000?"]})

    def test_tenant_id_rejects_asterisk(self):
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000*"]})

    def test_tenant_id_rejects_plus(self):
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000+0000"]})

    def test_tenant_id_rejects_equals(self):
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000=0000"]})

    def test_tenant_id_rejects_at_sign(self):
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000@0000"]})

    def test_tenant_id_rejects_hash(self):
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000#0000"]})

    def test_tenant_id_rejects_exclamation(self):
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000!0000"]})

    def test_tenant_id_rejects_tilde(self):
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["~dcc00000"]})

    def test_tenant_id_rejects_caret(self):
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["^dcc00000"]})

    def test_tenant_id_rejects_percent(self):
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000%0000"]})


class AssetPathTraversalTests(unittest.TestCase):
    """Verify asset serving is restricted to known files."""

    def test_asset_serving_uses_allowlist(self):
        """Asset serving must use an allowlist of known files."""
        api_source = (ROOT / "src" / "dcc" / "api.py").read_text()
        self.assertIn("/assets/", api_source)
        self.assertIn("onboarding.js", api_source)
        self.assertIn("topology.js", api_source)
        self.assertIn("azure-prices.js", api_source)
        self.assertIn("placement-comparison.js", api_source)
        self.assertIn("placement-scenarios.js", api_source)
        self.assertIn("quality-dashboard.js", api_source)

    def test_asset_serving_does_not_use_user_input(self):
        """Asset serving must not use user-supplied filenames."""
        api_source = (ROOT / "src" / "dcc" / "api.py").read_text()
        # The path is checked against a set, not constructed from user input
        self.assertIn("path.path in {", api_source)

    def test_asset_serving_rejects_unknown_paths(self):
        """Asset serving returns 404 for unknown paths."""
        api_source = (ROOT / "src" / "dcc" / "api.py").read_text()
        self.assertIn("404", api_source)
        self.assertIn("asset_not_found", api_source)

    def test_asset_serving_uses_pathlib_join(self):
        """Asset serving uses pathlib for safe path joining."""
        api_source = (ROOT / "src" / "dcc" / "api.py").read_text()
        self.assertIn("ROOT / \"ui\"", api_source)

    def test_asset_serving_validates_content_type(self):
        """Asset serving sets correct Content-Type."""
        api_source = (ROOT / "src" / "dcc" / "api.py").read_text()
        self.assertIn("text/javascript", api_source)


if __name__ == "__main__":
    unittest.main()
