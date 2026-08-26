from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
GENERATOR_PATH = REPO_ROOT / "scripts" / "generate_help.py"
CSS_SOURCE = REPO_ROOT / "docs" / "help" / "help.css"

EXPECTED_OUTPUTS = {
    "cli.html",
    "cli.zh-TW.html",
    "webui.html",
    "webui.zh-TW.html",
    "supported-models.html",
    "supported-models.zh-TW.html",
    "help.css",
}


def run_generator(output_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(GENERATOR_PATH), "--output-dir", str(output_dir)],
        capture_output=True,
        text=True,
        check=False,
    )


def load_generator_module():
    spec = importlib.util.spec_from_file_location("generate_help", GENERATOR_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_generated_bundle_contract(tmp_path: Path) -> None:
    output_dir = tmp_path / "help"
    result = run_generator(output_dir)
    assert result.returncode == 0, result.stderr

    assert {item.name for item in output_dir.iterdir()} == EXPECTED_OUTPUTS

    en_pages = ["cli.html", "webui.html", "supported-models.html"]
    zh_pages = ["cli.zh-TW.html", "webui.zh-TW.html", "supported-models.zh-TW.html"]

    for name in en_pages:
        page_bytes = (output_dir / name).read_bytes()
        assert b"\r\n" not in page_bytes
        page = page_bytes.decode("utf-8")
        assert 'lang="en"' in page
        assert "{{HELP_" not in page
        assert 'href="help.css"' in page
        assert "<h1" in page

    for name in zh_pages:
        page_bytes = (output_dir / name).read_bytes()
        assert b"\r\n" not in page_bytes
        page = page_bytes.decode("utf-8")
        assert 'lang="zh-TW"' in page
        assert "{{HELP_" not in page
        assert 'href="help.css"' in page
        assert "<h1" in page

    generated_css = (output_dir / "help.css").read_bytes()
    assert b"\r\n" not in generated_css
    assert generated_css == CSS_SOURCE.read_bytes()


def test_internal_help_links_and_markdown_structures(tmp_path: Path) -> None:
    output_dir = tmp_path / "help"
    result = run_generator(output_dir)
    assert result.returncode == 0, result.stderr

    en_pages = [
        (output_dir / name).read_text(encoding="utf-8") for name in ("cli.html", "webui.html")
    ]
    zh_pages = [
        (output_dir / name).read_text(encoding="utf-8")
        for name in ("cli.zh-TW.html", "webui.zh-TW.html")
    ]

    for page in en_pages:
        assert 'href="supported-models.html' in page
    for page in zh_pages:
        assert 'href="supported-models.zh-TW.html' in page
    for page in (*en_pages, *zh_pages):
        assert "../core/supported-models" not in page

    supported_models = (output_dir / "supported-models.html").read_text(encoding="utf-8")
    assert "<table" in supported_models
    assert re.search(r'<h3\b[^>]*\bid="[^"]+"', supported_models)


def test_javascript_label_escaping_roundtrip() -> None:
    generator = load_generator_module()
    sample = '複製 "value" \\ path\n下一行'
    escaped = generator.escape_javascript_string(sample)
    assert json.loads('"' + escaped + '"') == sample


def test_help_theme_preference_bridge(tmp_path: Path) -> None:
    output_dir = tmp_path / "help"
    result = run_generator(output_dir)
    assert result.returncode == 0, result.stderr

    css = (output_dir / "help.css").read_text(encoding="utf-8")
    assert ':root[data-theme="dark"]' in css
    assert "prefers-color-scheme: dark" in css
    assert ':root[data-theme="system"]' in css

    for name in ("webui.html", "webui.zh-TW.html", "supported-models.html", "supported-models.zh-TW.html"):
        page = (output_dir / name).read_text(encoding="utf-8")
        assert "meters-tool.webui.theme" in page
        assert "URLSearchParams" in page
        # Query theme must be resolved before cookie fallback.
        assert page.index("URLSearchParams") < page.index("document.cookie")
        # Theme query must be resolved before stylesheet.
        assert page.index("meters-tool.webui.theme") < page.index('href="help.css"')
        # Valid query theme must override cookie and propagate to Help HTML links.
        assert 'searchParams.set("theme"' in page or "searchParams.set('theme'" in page
        assert 'a[href]' in page


def test_tracked_webui_help_runtime_bundle_matches_generator(tmp_path: Path) -> None:
    output_dir = tmp_path / "help"
    result = run_generator(output_dir)
    assert result.returncode == 0, result.stderr

    runtime_help_dir = REPO_ROOT / "src" / "meters_tool_webui" / "static" / "help"
    assert runtime_help_dir.is_dir(), f"WebUI runtime Help directory is missing: {runtime_help_dir}"

    webui_runtime_files = [
        "webui.html",
        "webui.zh-TW.html",
        "supported-models.html",
        "supported-models.zh-TW.html",
        "help.css",
    ]
    for name in webui_runtime_files:
        fresh = (output_dir / name).read_bytes()
        tracked = (runtime_help_dir / name).read_bytes()
        assert fresh == tracked, f"tracked WebUI Help asset is stale: {name}"
        # Also guard that no cli artifacts were copied into WebUI static tree
    assert not (runtime_help_dir / "cli.html").exists()
    assert not (runtime_help_dir / "cli.zh-TW.html").exists()
