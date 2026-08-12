from __future__ import annotations

import re
from pathlib import Path


STATIC_DIR = Path(__file__).parents[2] / "src" / "meters_tool_webui" / "static"


def load_static_ui():
    return (
        (STATIC_DIR / "index.html").read_text(encoding="utf-8"),
        (STATIC_DIR / "app.js").read_text(encoding="utf-8"),
    )


def assert_tag_with_attrs(testcase, html, tag, attrs):
    lookaheads = "".join(
        rf"(?=[^>]*\b{re.escape(name)}=\"{re.escape(value)}\")"
        for name, value in attrs.items()
    )
    testcase.assertRegex(html, rf"<{tag}\b{lookaheads}[^>]*>")


def make_api_client(testcase):
    import tempfile

    from fastapi.testclient import TestClient

    from meters_tool_webui.web_ui import WebRunManager, create_app

    testcase.tempdir = tempfile.TemporaryDirectory()
    csv_path = Path(testcase.tempdir.name) / "out.csv"
    return TestClient(create_app(WebRunManager())), csv_path


def make_api_client_with_manager(manager):
    from fastapi.testclient import TestClient

    from meters_tool_webui.web_ui import create_app

    return TestClient(create_app(manager))


def wait_until_inactive(client, timeout_s=1.0):
    import time

    deadline = time.monotonic() + timeout_s
    status = client.get("/api/runs/current").json()
    while status.get("active") and time.monotonic() < deadline:
        time.sleep(0.02)
        status = client.get("/api/runs/current").json()
    return status


def cleanup_tempdir(testcase):
    tempdir = getattr(testcase, "tempdir", None)
    if tempdir is not None:
        tempdir.cleanup()
