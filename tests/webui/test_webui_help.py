from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from meters_tool_webui.web_ui import create_app


def _create_help_bundle(directory: Path) -> dict[str, str]:
    markers = {
        "webui.html": "<html>en help marker</html>",
        "webui.zh-TW.html": "<html>zh-TW help marker</html>",
        "supported-models.html": "<html>supported models marker</html>",
        "supported-models.zh-TW.html": "<html>zh-TW supported models marker</html>",
        "help.css": "/* help css marker */",
    }
    for name, content in markers.items():
        (directory / name).write_text(content, encoding="utf-8")
    return markers


class WebUiHelpTests(unittest.TestCase):
    def test_help_bundle_served_with_no_store(self):
        with tempfile.TemporaryDirectory() as tmp:
            help_dir = Path(tmp) / "help"
            help_dir.mkdir(parents=True)
            markers = _create_help_bundle(help_dir)
            client = TestClient(create_app(help_dir=help_dir))

            response = client.get("/help/")
            self.assertEqual(response.status_code, 200)
            self.assertIn(markers["webui.html"], response.text)
            self.assertEqual(response.headers.get("Cache-Control"), "no-store")

            response = client.get("/help/webui.zh-TW.html")
            self.assertEqual(response.status_code, 200)
            self.assertIn(markers["webui.zh-TW.html"], response.text)
            self.assertEqual(response.headers.get("Cache-Control"), "no-store")

            response = client.get("/help/supported-models.html")
            self.assertEqual(response.status_code, 200)
            self.assertIn(markers["supported-models.html"], response.text)

            response = client.get("/help/help.css")
            self.assertEqual(response.status_code, 200)
            self.assertIn(markers["help.css"], response.text)

            response = client.get("/help/missing.html")
            self.assertEqual(response.status_code, 404)

    def test_missing_help_bundle_does_not_break_webui(self):
        with tempfile.TemporaryDirectory() as tmp:
            help_dir = Path(tmp) / "missing-help"
            # do not create directory
            client = TestClient(create_app(help_dir=help_dir))

            response = client.get("/")
            self.assertEqual(response.status_code, 200)

            response = client.get("/help/")
            self.assertEqual(response.status_code, 404)

            response = client.get("/help/help.css")
            self.assertEqual(response.status_code, 404)

    def test_default_webui_runtime_serves_real_help_bundle(self):
        client = TestClient(create_app())

        response = client.get("/help/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Cache-Control"), "no-store")
        self.assertNotIn("{{HELP_", response.text)
        self.assertIn('href="help.css"', response.text)

        for path in (
            "/help/webui.zh-TW.html",
            "/help/supported-models.html",
            "/help/supported-models.zh-TW.html",
            "/help/help.css",
        ):
            with self.subTest(path=path):
                resp = client.get(path)
                self.assertEqual(resp.status_code, 200)
                self.assertNotIn("{{HELP_", resp.text if "css" not in path else "")
                if path.endswith(".css"):
                    self.assertTrue(len(resp.text) > 100)



if __name__ == "__main__":
    unittest.main()
