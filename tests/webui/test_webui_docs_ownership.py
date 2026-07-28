from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DOC_ROOT = REPO_ROOT / "docs" / "webui"
def read_doc(*parts: str) -> str:
    return DOC_ROOT.joinpath(*parts).read_text(encoding="utf-8")


def test_webui_docs_are_package_local():
    assert (DOC_ROOT / "README.md").exists()

    for path in (
        "USER_GUIDE.md",
        "localization-contract.md",
        "web-ui-change-rules.md",
    ):
        assert (DOC_ROOT / path).exists()

    assert not (DOC_ROOT / f"Webui-{'README'}.md").exists()
    assert not (DOC_ROOT / f"web-ui-{'ai'}-change-rules.md").exists()

    cli_docs = (
        "docs/cli-integration.md",
        f"docs/cli-{'jsonl'}-contract.md",
        f"docs/common-cli-{'jsonl'}-contract.md",
        f"docs/meters-cli-{'jsonl'}-contract.md",
        f"docs/common-{'worker'}-protocol.md",
        f"docs/meters-worker-{'contract'}.md",
        f"docs/common-{'orchestrator'}-workflows.md",
        f"docs/meters-{'orchestrator'}-workflows.md",
        f"docs/worker-{'contract'}.md",
        f"docs/README_CLI_{'EN'}.md",
    )
    for cli_doc in cli_docs:
        assert not (DOC_ROOT / cli_doc).exists()


def test_webui_readme_uses_webui_entrypoint_not_cli_workflow():
    text = read_doc("README.md")

    assert "meters-tool.exe" not in text
    assert "python -m meters_tool_cli" not in text
    assert "python -m meters_tool_webui.web_ui" not in text
    assert "pip install -r" not in text
    assert "requirements.txt" not in text
    assert "uv sync" not in text
    assert "start-trigger-record" not in text
    assert "meters-tool-webui" in text


def test_webui_docs_point_to_new_import_and_static_paths():
    text = "\n".join(
        read_doc(*path)
        for path in (
            ("README.md",),
            ("web-ui-change-rules.md",),
        )
    )

    assert "meters_tool_webui" in text
    assert "meters_tool_core" in text
    assert "src/meters_tool_webui/static" in text


def test_webui_maintainer_docs_link_to_localization_contract():
    link = "[WebUI Localization Contract](localization-contract.md)"

    assert link in read_doc("README.md")
    assert link in read_doc("web-ui-change-rules.md")


def test_webui_localization_contract_records_stable_locale_decisions():
    text = read_doc("localization-contract.md")

    for token in (
        'SOURCE_LOCALE = "en"',
        'FALLBACK_LOCALE = "en"',
        'SUPPORTED_LOCALES = ["en", "zh-TW"]',
        'LOCALE_STORAGE_KEY = "meters-tool.webui.locale"',
        "`preserve_raw`",
        "`machine_value`",
    ):
        assert token in text
