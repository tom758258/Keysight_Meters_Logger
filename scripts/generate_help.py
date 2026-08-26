from __future__ import annotations

import argparse
import html
import json
import re
import shutil
from pathlib import Path

import markdown
from markdown.extensions.toc import TocExtension, slugify_unicode


REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_RELATIVE_PATH = "docs/help/template.html"
STYLESHEET_RELATIVE_PATH = "docs/help/help.css"

HELP_SOURCES = (
    ("docs/cli/USER_GUIDE.md", "cli.html", "en"),
    ("docs/cli/USER_GUIDE.zh-TW.md", "cli.zh-TW.html", "zh-TW"),
    ("docs/webui/USER_GUIDE.md", "webui.html", "en"),
    ("docs/webui/USER_GUIDE.zh-TW.md", "webui.zh-TW.html", "zh-TW"),
    ("docs/core/supported-models.md", "supported-models.html", "en"),
    ("docs/core/supported-models.zh-TW.md", "supported-models.zh-TW.html", "zh-TW"),
)

HELP_CHROME = {
    "en": {
        "toc_label": "Contents",
        "copy_label": "Copy",
        "copied_label": "Copied",
    },
    "zh-TW": {
        "toc_label": "章節導覽",
        "copy_label": "複製",
        "copied_label": "已複製",
    },
}

REQUIRED_PLACEHOLDERS = (
    "{{HELP_LANG}}",
    "{{HELP_TITLE}}",
    "{{HELP_TOC_LABEL}}",
    "{{HELP_COPY_LABEL}}",
    "{{HELP_COPIED_LABEL}}",
    "{{HELP_CONTENT}}",
)

HELP_LINK_REWRITES = (
    ('href="../core/supported-models.zh-TW.md', 'href="supported-models.zh-TW.html'),
    ('href="../core/supported-models.md', 'href="supported-models.html'),
)


def escape_html_attribute(value: str) -> str:
    return html.escape(value, quote=True)


def escape_html_text(value: str) -> str:
    return html.escape(value, quote=False)


def escape_javascript_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)[1:-1]


def fail(message: str) -> None:
    raise SystemExit(f"Error: {message}")


def load_help_template() -> str:
    template_path = REPO_ROOT / TEMPLATE_RELATIVE_PATH
    if not template_path.is_file():
        fail(f"Help template not found: {TEMPLATE_RELATIVE_PATH}")
    template = template_path.read_text(encoding="utf-8")
    for placeholder in REQUIRED_PLACEHOLDERS:
        if template.count(placeholder) != 1:
            fail(f"Help template must contain {placeholder} exactly once.")
    return template


def extract_document_title(markdown_text: str, source_name: str) -> str:
    match = re.search(r"^#\s+(.+?)\s*$", markdown_text, re.MULTILINE)
    if match is None:
        fail(f"Help source has no level-1 heading: {source_name}")
    return match.group(1).strip()


def render_markdown(markdown_text: str) -> str:
    return markdown.markdown(
        markdown_text,
        extensions=[
            "fenced_code",
            "tables",
            "sane_lists",
            TocExtension(slugify=slugify_unicode),
        ],
    )


def rewrite_help_links(rendered_html: str) -> str:
    for source_href, target_href in HELP_LINK_REWRITES:
        rendered_html = rendered_html.replace(source_href, target_href)
    return rendered_html


def render_page(
    template: str,
    *,
    lang: str,
    title: str,
    chrome: dict[str, str],
    content: str,
) -> str:
    rendered = template.replace("{{HELP_LANG}}", escape_html_attribute(lang))
    rendered = rendered.replace("{{HELP_TITLE}}", escape_html_text(title))
    rendered = rendered.replace("{{HELP_TOC_LABEL}}", escape_html_text(chrome["toc_label"]))
    rendered = rendered.replace(
        "{{HELP_COPY_LABEL}}", escape_javascript_string(chrome["copy_label"])
    )
    rendered = rendered.replace(
        "{{HELP_COPIED_LABEL}}", escape_javascript_string(chrome["copied_label"])
    )
    rendered = rendered.replace("{{HELP_CONTENT}}", content)
    if "{{HELP_" in rendered:
        fail("Unresolved Help template placeholder after rendering.")
    return rendered


def generate_help_bundle(output_dir: Path) -> None:
    template = load_help_template()
    stylesheet_path = REPO_ROOT / STYLESHEET_RELATIVE_PATH
    if not stylesheet_path.is_file():
        fail(f"Help stylesheet not found: {STYLESHEET_RELATIVE_PATH}")

    output_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(stylesheet_path, output_dir / "help.css")

    for source_name, output_name, lang in HELP_SOURCES:
        source_path = REPO_ROOT / source_name
        if not source_path.is_file():
            fail(f"Help source not found: {source_name}")
        markdown_text = source_path.read_text(encoding="utf-8")
        title = extract_document_title(markdown_text, source_name)
        content = rewrite_help_links(render_markdown(markdown_text))
        page = render_page(template, lang=lang, title=title, chrome=HELP_CHROME[lang], content=content)
        (output_dir / output_name).write_text(page, encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Generate the offline Help bundle from canonical Markdown sources."
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory that receives the flat generated Help bundle.",
    )
    arguments = parser.parse_args(argv)
    generate_help_bundle(Path(arguments.output_dir))


if __name__ == "__main__":
    main()
