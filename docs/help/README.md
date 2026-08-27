# Help Maintenance

This document is for maintainers and contributors. It describes the current
source-of-truth and synchronization workflow for bundled offline Help.

## Sources and Presentation

Canonical Help content is maintained in these Markdown files:

- `docs/cli/USER_GUIDE.md`
- `docs/cli/USER_GUIDE.zh-TW.md`
- `docs/webui/USER_GUIDE.md`
- `docs/webui/USER_GUIDE.zh-TW.md`
- `docs/core/supported-models.md`
- `docs/core/supported-models.zh-TW.md`

Shared presentation sources are:

- `docs/help/template.html`
- `docs/help/help.css`

The generator is `scripts/generate_help.py`. It produces one complete flat
generated Help bundle in the requested output directory. Generate to a staging
directory first; do not run it directly into either tracked runtime Help
directory.

For example:

```powershell
uv run python scripts/generate_help.py `
    --output-dir .tmp_tests\generated_help
```

After generation, synchronize only the frontend-owned subset into the tracked
runtime directories. Never hand-edit generated Help HTML.

## Runtime Ownership

CLI runtime Help in `src/meters_tool_cli/help/` owns:

- `cli.html`
- `cli.zh-TW.html`
- `supported-models.html`
- `supported-models.zh-TW.html`
- `help.css`

WebUI runtime Help in `src/meters_tool_webui/static/help/` owns:

- `webui.html`
- `webui.zh-TW.html`
- `supported-models.html`
- `supported-models.zh-TW.html`
- `help.css`

Desktop reuses WebUI Help and has no separate Help content set. Do not
recreate the removed legacy documentation HTML mirrors.

Validate the generated bundle and tracked runtime synchronization with
`tests/help/test_generate_help.py`.
