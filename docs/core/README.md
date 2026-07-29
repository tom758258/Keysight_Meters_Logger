# Meters Tool Core

Core contains the public API and acquisition runtime contract used by the CLI
and WebUI components for supported digital multimeter integrations.

Core owns the shared request model, validation, dry-run planning, runtime
session orchestration, event/result types, control-plane interfaces, profile
metadata, and safety rules for the Meters Tool acquisition runtime. It is
shipped inside the single `meters-tool` distribution while preserving the
`meters_tool_core` import boundary.

Core can carry an optional `visa_library` value through `StartRequest` and
`InstrumentConfig`. When it is unset, live VISA sessions use
`pyvisa.ResourceManager()` and therefore the system default VISA runtime. CLI
diagnostics may pass values such as `@py`; WebUI runs leave it unset.

Current support scope is:

- 34461A: validated USB/system VISA, LAN/system VISA, and CLI-only
  LAN/TCPIP with pyvisa-py `@py`.
- 34460A: USB/system VISA is open for the currently approved workflows,
  including the explicitly promoted DCV Ratio scope. LAN/TCPIP scopes remain
  pending.

Stable model identity is:

| Instrument | Stable model ID |
| --- | --- |
| `34461A` | `keysight-34461a` |
| `34460A` | `keysight-34460a` |

See [Core Integration](integration.md) and
[Supported Models](supported-models.md) for the detailed identity and support
rules.

For CLI/WebUI starts, `StartRequest.instrument_model = None` means auto-detect
for live resources. Adapters may resolve the connected profile with an IDN-only
preflight before validation and planning, but that preflight is not the final
safety boundary. `run_start_session()` performs Core-owned runtime profile
resolution, request validation, and the final support-policy gate again. Dry-
run and simulator starts must use an explicit model unless the simulator
resource deterministically names one, such as `SIM::34460A` or `SIM::34461A`.

Normal CLI, WebUI, and Core starts use Product mode, which requires the exact
scope and requested features to be product-open. Maintainer-only Validation
mode can execute only explicitly registered pending transport or feature
scopes for evidence collection. Passing validation artifacts does not promote
public support automatically. The simulator provides deterministic contract
and workflow validation only; it is not evidence of live measurement accuracy
or hardware support.

The CLI and WebUI components own their command-line, web, wrapper, and
serialization layers. Core must not import `meters_tool_cli` or
`meters_tool_webui`.

## Validation

No-hardware Core validation:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/core -q -p no:cacheprovider
```

Core validation should not require CLI or WebUI imports except through tests
that explicitly check the component boundary.

## Documentation

- [Core Integration](integration.md)
- [Supported Models](supported-models.md)
- [Changelog](../../CHANGELOG.md)
