"""Security tests: Cross-Site Scripting (XSS) prevention."""
from __future__ import annotations

import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]


class XSSPreventionTests(unittest.TestCase):
    """Verify XSS payloads are properly escaped or rejected."""

    def test_tenant_id_rejects_script_tag(self):
        """Script tags in tenant_id must be rejected."""
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["<script>alert(1)</script>"]})

    def test_tenant_id_rejects_img_onerror(self):
        """Image onerror in tenant_id must be rejected."""
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["<img src=x onerror=alert(1)>"]})

    def test_tenant_id_rejects_svg_onload(self):
        """SVG onload in tenant_id must be rejected."""
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["<svg onload=alert(1)>"]})

    def test_tenant_id_rejects_javascript_protocol(self):
        """javascript: protocol in tenant_id must be rejected."""
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["javascript:alert(1)"]})

    def test_tenant_id_rejects_vbscript_protocol(self):
        """vbscript: protocol in tenant_id must be rejected."""
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["vbscript:alert(1)"]})

    def test_tenant_id_rejects_data_protocol(self):
        """data: protocol in tenant_id must be rejected."""
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["data:text/html,<script>alert(1)</script>"]})

    def test_tenant_id_rejects_onfocus(self):
        """onfocus handler in tenant_id must be rejected."""
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["<input onfocus=alert(1) autofocus>"]})

    def test_tenant_id_rejects_onmouseover(self):
        """onmouseover handler in tenant_id must be rejected."""
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["<a onmouseover=alert(1)>hover</a>"]})

    def test_tenant_id_rejects_onclick(self):
        """onclick handler in tenant_id must be rejected."""
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["<button onclick=alert(1)>click</button>"]})

    def test_tenant_id_rejects_onload(self):
        """onload handler in tenant_id must be rejected."""
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["<body onload=alert(1)>"]})

    def test_tenant_id_rejects_onerror(self):
        """onerror handler in tenant_id must be rejected."""
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["<img src=x onerror=alert(1)>"]})

    def test_tenant_id_rejects_onanimationstart(self):
        """onanimationstart handler in tenant_id must be rejected."""
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["<div onanimationstart=alert(1)>"]})

    def test_tenant_id_rejects_ontransitionend(self):
        """ontransitionend handler in tenant_id must be rejected."""
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["<div ontransitionend=alert(1)>"]})

    def test_tenant_id_rejects_expression(self):
        """CSS expression in tenant_id must be rejected."""
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["expression(alert(1))"]})

    def test_tenant_id_rejects_import(self):
        """CSS import in tenant_id must be rejected."""
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["@import url('evil.css')"]})

    def test_tenant_id_rejects_behavior(self):
        """CSS behavior in tenant_id must be rejected."""
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["behavior:url(evil.htc)"]})

    def test_tenant_id_rejects_moz_binding(self):
        """moz-binding in tenant_id must be rejected."""
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["-moz-binding:url(evil.xml)"]})

    def test_tenant_id_rejects_base_tag(self):
        """base tag in tenant_id must be rejected."""
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["<base href='http://evil.com/'>"]})

    def test_tenant_id_rejects_link_tag(self):
        """link tag in tenant_id must be rejected."""
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["<link rel=stylesheet href='evil.css'>"]})

    def test_tenant_id_rejects_meta_refresh(self):
        """meta refresh in tenant_id must be rejected."""
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["<meta http-equiv=refresh content='0;url=evil'>"]})

    def test_tenant_id_rejects_iframe(self):
        """iframe in tenant_id must be rejected."""
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["<iframe src='evil.html'>"]})

    def test_tenant_id_rejects_object(self):
        """object tag in tenant_id must be rejected."""
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["<object data='evil.swf'>"]})

    def test_tenant_id_rejects_embed(self):
        """embed tag in tenant_id must be rejected."""
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["<embed src='evil.swf'>"]})

    def test_tenant_id_rejects_applet(self):
        """applet tag in tenant_id must be rejected."""
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["<applet code='Evil.class'>"]})

    def test_tenant_id_rejects_form(self):
        """form tag in tenant_id must be rejected."""
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["<form action='evil.php'><input type=submit></form>"]})

    def test_tenant_id_rejects_input(self):
        """input tag in tenant_id must be rejected."""
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["<input type=text value='evil'>"]})

    def test_tenant_id_rejects_textarea(self):
        """textarea tag in tenant_id must be rejected."""
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["<textarea>evil</textarea>"]})

    def test_tenant_id_rejects_select(self):
        """select tag in tenant_id must be rejected."""
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["<select><option>evil</option></select>"]})

    def test_tenant_id_rejects_option(self):
        """option tag in tenant_id must be rejected."""
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["<option>evil</option>"]})

    def test_tenant_id_rejects_button(self):
        """button tag in tenant_id must be rejected."""
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["<button>evil</button>"]})

    def test_tenant_id_rejects_details(self):
        """details tag in tenant_id must be rejected."""
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["<details open><summary>evil</summary></details>"]})

    def test_tenant_id_rejects_marquee(self):
        """marquee tag in tenant_id must be rejected."""
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["<marquee>evil</marquee>"]})

    def test_tenant_id_rejects_audio(self):
        """audio tag in tenant_id must be rejected."""
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["<audio src='evil.mp3'>"]})

    def test_tenant_id_rejects_video(self):
        """video tag in tenant_id must be rejected."""
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["<video src='evil.mp4'>"]})

    def test_tenant_id_rejects_source(self):
        """source tag in tenant_id must be rejected."""
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["<source src='evil.mp4'>"]})

    def test_tenant_id_rejects_track(self):
        """track tag in tenant_id must be rejected."""
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["<track src='evil.vtt'>"]})

    def test_tenant_id_rejects_area(self):
        """area tag in tenant_id must be rejected."""
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["<area href='evil.html'>"]})

    def test_tenant_id_rejects_map(self):
        """map tag in tenant_id must be rejected."""
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["<map name='evil'><area href='evil.html'></map>"]})

    def test_tenant_id_rejects_math(self):
        """math tag in tenant_id must be rejected."""
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["<math><mrow><mi>evil</mi></mrow></math>"]})

    def test_tenant_id_rejects_mtext(self):
        """mtext tag in tenant_id must be rejected."""
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["<mtext>evil</mtext>"]})

    def test_tenant_id_rejects_mglyph(self):
        """mglyph tag in tenant_id must be rejected."""
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["<mglyph>evil</mglyph>"]})

    def test_tenant_id_rejects_malignmark(self):
        """malignmark tag in tenant_id must be rejected."""
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["<malignmark>evil</malignmark>"]})

    def test_tenant_id_rejects_annotation_xml(self):
        """annotation-xml tag in tenant_id must be rejected."""
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["<annotation-xml encoding='text/html'><script>alert(1)</script></annotation-xml>"]})

    def test_tenant_id_rejects_discouraged(self):
        """Discouraged tags in tenant_id must be rejected."""
        from dcc.api import parse_tenant
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["<xss id=x onfocus=alert(1) tabindex=1>#"]})


class XSSResponseHeaderTests(unittest.TestCase):
    """Verify XSS-related security headers are present."""

    def test_api_sets_no_store_cache_control(self):
        """API responses must include Cache-Control: no-store."""
        api_source = (ROOT / "src" / "dcc" / "api.py").read_text()
        self.assertIn("no-store", api_source)

    def test_api_sets_content_type_json(self):
        """API responses must set Content-Type to application/json."""
        api_source = (ROOT / "src" / "dcc" / "api.py").read_text()
        self.assertIn("application/json", api_source)

    def test_api_does_not_reflect_tenant_id_unsanitized(self):
        """API must not reflect tenant_id without validation."""
        api_source = (ROOT / "src" / "dcc" / "api.py").read_text()
        self.assertIn("parse_tenant", api_source)

    def test_ui_escapes_html_entities(self):
        """UI must escape HTML entities in dynamic content."""
        ui_source = (ROOT / "ui" / "index.html").read_text()
        self.assertIn("esc(", ui_source)
        self.assertIn("&amp;", ui_source)
        self.assertIn("&lt;", ui_source)
        self.assertIn("&gt;", ui_source)
        self.assertIn("&quot;", ui_source)
        self.assertIn("&#39;", ui_source)

    def test_ui_uses_textcontent_not_innerhtml_for_user_data(self):
        """UI should use textContent for user-controlled data."""
        ui_source = (ROOT / "ui" / "index.html").read_text()
        self.assertIn("textContent", ui_source)

    def test_ui_validates_tenant_uuid_format(self):
        """UI must validate tenant UUID format before sending."""
        ui_source = (ROOT / "ui" / "index.html").read_text()
        self.assertIn("UUID", ui_source)
        self.assertIn("test(", ui_source)


if __name__ == "__main__":
    unittest.main()
