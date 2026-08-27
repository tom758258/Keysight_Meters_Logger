# Meters Tool CLI User Guide

This guide is for operators who receive the built CLI executable or an
already-installed `meters-tool` command and use it to record measurements
from a supported digital multimeter. It focuses on the normal measurement workflow and common settings.

## Start The CLI

For a release build, extract `meters-tool-<version>-windows-x64.zip`, open
PowerShell in the extracted `meters-tool-<version>` folder, and check the CLI:

```powershell
.\meters-tool.exe --version
```

The executable name remains unversioned inside the versioned bundle folder.

## Open The User Guide

The release CLI can open its bundled offline User Guide in the default browser:

```powershell
.\meters-tool.exe user-guide
.\meters-tool.exe user-guide --lang en
.\meters-tool.exe user-guide --lang zh-TW
```

The default guide language is English. Use `--lang zh-TW` for Traditional
Chinese. The guide is bundled with the CLI and does not require an online
documentation site. For exact command options, accepted values, ranges, or
defaults, use `.\meters-tool.exe <command> --help`.

## First Live Run

Use this flow when checking a new computer, VISA runtime, connection, or
instrument setup.

Before a real live run, ensure no other Meters CLI, WebUI, logger, test
process, or external VISA application is controlling the same physical
instrument. Concurrent control can interfere with SCPI responses or instrument
state. Meters Tool does not enforce this with an automatic lock.

1. Turn on the Keysight 34460A or 34461A and connect it to the computer.
2. List resources that currently answer `*IDN?`:

```powershell
.\meters-tool.exe list-resources --live-only
```

3. Copy the resource string for the instrument and set it once for this
   PowerShell session:

```powershell
$env:METER_RESOURCE = "USB0::...::INSTR"
```

   The value can be any live VISA resource returned by discovery, including
   USB or TCPIP/LAN resources.

4. Run one bounded immediate-mode sample:

```powershell
.\meters-tool.exe start-trigger-record `
  --resource "$env:METER_RESOURCE" `
  --measurement voltage-dc `
  --trigger-mode immediate `
  --max-samples 1 `
  --csv ".\data\cli_smoke.csv"
```

5. Confirm the command exits, the CSV file exists, and the CSV has one data
   row.
6. Compare the CSV value with the front-panel reading before trusting longer
   captures.

Use an explicit `--resource` value for live acquisition. Passing
`"$env:METER_RESOURCE"` still gives the CLI an explicit resource; do
not rely on a script or unattended workflow to guess which instrument should be
used.

Live starts auto-detect 34460A or 34461A from the connected instrument IDN when
`--model` is omitted. Add `--model 34460A` or `--model 34461A` only when Start
must require that IDN match; a live mismatch fails before setup, and the
selected model never overrides the IDN-selected profile. `--model` also accepts
the stable IDs `keysight-34460a` and `keysight-34461a`. In live mode, any
model value remains an expected-model guard and does not unlock another support
scope. Dry-run and simulate commands use the selected model profile and need
`--model` unless the resource is the deterministic simulator resource
`SIM::34460A` or `SIM::34461A`. Model names are normalized and validated by Core
profile logic, so unknown models fail with a clear validation error.

## Live Support Scope Reminder

A VISA resource that answers `*IDN?` or appears in `list-resources` is not by
itself Product-open for every model and transport/backend combination. Model,
transport, backend, measurement, and trigger support are exact and must match
Core policy. Unsupported combinations fail closed instead of being unlocked by
`--model` or a scan result.

For the exact current support matrix, see [Supported Models](../core/supported-models.md).

By default, the CLI uses the computer's System VISA runtime, such as Keysight
IO Libraries Suite or NI-VISA. Backend selection does not change or expand
Product support. The bundled Windows CLI executable supports only the fixed
System VISA path and does not bundle optional backends.

## Choosing A Measurement

Choose the measurement type that matches the instrument wiring and the signal
being measured:

- `voltage-dc`: DC voltage.
- `voltage-dc-ratio`: DC voltage ratio.
- `current-dc`: DC current.
- `voltage-ac`: AC voltage.
- `current-ac`: AC current.
- `frequency`: signal frequency in Hz.
- `period`: signal period in seconds.
- `resistance-2w`: 2-wire resistance.
- `resistance-4w`: 4-wire resistance.

Confirm the input terminals before measuring current or 4-wire resistance.
For AC, Frequency, and Period modes, run a low-risk smoke test and compare the
CSV value with the front-panel reading before using the setup for longer
captures.

## Choosing A Trigger Mode

Use `--trigger-mode immediate` for the simplest workflow. The instrument starts
capturing when the run starts. Add `--max-samples` unless you intentionally want
a continuous run.

Use `--trigger-mode software` when the run should wait for software trigger
commands. Start the logger in one terminal, then send triggers from another:

```powershell
.\meters-tool.exe send-command
```

Use timer capture when the run should take software-triggered readings on a
schedule. Set the timer interval explicitly and keep the run bounded while
validating the setup.

Use external or hardware trigger modes only when the physical trigger signal is
connected and the operator understands the trigger edge and delay settings.
Hardware trigger timeout is a protective re-arm condition, not automatically a
failed measurement.

## Common Settings

`--resource` is the VISA address of the instrument. Use a value returned by
`list-resources --live-only` or a known operator-provided resource. In
PowerShell examples, set `$env:METER_RESOURCE` once and pass
`--resource "$env:METER_RESOURCE"` so copied commands continue to use
the selected instrument.

`--visa-library` is an advanced CLI backend selector. Omit it for normal Product use and rely on System VISA.
Selecting a backend does not unlock unsupported models, transports, measurements, or other Product support.

`list-resources --verify` opens discovered VISA resources and queries `*IDN?`.
`list-resources --live-only` implies verification and hides stale entries.
ASRL/RS-232 verification uses a short bounded timeout so a stale serial entry
does not block later USB or TCPIP resources. The serial termination options
`--serial-read-termination` and `--serial-write-termination` are CLI discovery
compatibility settings for ASRL verification only; they are not acquisition
settings.

`--csv` is the output file path. If omitted, the CLI creates a timestamped CSV
path. Use an explicit path when you need predictable file locations for review
or automation. Use `--no-csv` to disable CSV output for a run; it cannot be combined with `--csv`.

`--max-samples` bounds simple runs. Use it during smoke tests and validation so
the command stops by itself.

`--auto-range` lets the instrument choose the range. Keep Auto Range enabled
unless the measurement setup requires a fixed range.

`--range` selects a manual range when Auto Range is disabled. Choose a range
that safely covers the expected signal.

`--nplc` controls integration time for DC and resistance measurements. Higher
values are slower and can be more stable. AC, Frequency, and Period modes
accept only the neutral default because they do not write NPLC SCPI.

`--auto-zero` controls offset handling for DC and resistance measurements.
It can improve accuracy but may slow readings. AC, Frequency, and Period modes
do not write Auto Zero SCPI.

`--ac-bandwidth-hz` applies to AC voltage, AC current, Frequency, and Period.
Frequency and Period default to `20` Hz.

`--gate-time-s` applies only to Frequency and Period. Choose `0.01`, `0.1`, or
`1` second; the default is `0.1` second.

`--freq-period-timeout` applies only to Frequency. Keep the default `auto`
unless the measurement procedure requires the `1s` behavior. Period does not
send a timeout command; specifying this option with Period is rejected.

`--current-terminal` applies to current measurements. Match it to the physical
current terminal used on the instrument.

`--trigger-timeout-ms` controls how long trigger workflows wait before the
protective timeout path is used. Increase it only when the measurement setup
intentionally waits longer.

For command options and CLI-level accepted values, ranges, and defaults, run
`meters-tool <command> --help` (for example,
`.\meters-tool.exe start-trigger-record --help`).
Model-specific support and limits remain subject to Core validation and the
Supported Models scope described above.

## CSV Output

With the default CSV output enabled, each captured sample is written as one
row. Check the CSV after a smoke run for:

- at least one data row;
- expected `measurement_type`;
- expected `unit`;
- expected `trigger_source`;
- a value that matches the front panel closely enough for the test setup.

The CSV is flushed after each captured sample, so completed rows should be
available even during longer runs.

## Stop A Run

For bounded validation runs, prefer `--max-samples` so the run stops by itself.

For a running worker, use one of these stop paths:

- press `q` in the logger terminal;
- press `Ctrl+C` or `Ctrl+Break`;
- run the stop command from another terminal:

```powershell
.\meters-tool.exe stop
```

After stopping, confirm the command exits cleanly and the CSV contains the
expected rows.

## Common Problems

If `meters-tool.exe` is missing, fully extract the ZIP, open the versioned
release folder, and confirm that `meters-tool.exe` exists there.

If `list-resources` shows stale resources, use `list-resources --verify` to see
which resources answer and why others failed. Use `--live-only` when you only
want resources that answered `*IDN?`. If an ASRL/RS-232 resource reports a
termination-related stale result, retry discovery with
`--serial-read-termination` or `--serial-write-termination`; those options only
affect ASRL verification.

If no live resource is found, check instrument power, USB/LAN/GPIB connection,
VISA driver visibility, and whether another program is holding the instrument.

If a run is blocked before opening the instrument, read the validation error and
adjust the option it names. The CLI validates common settings before live I/O.

If a hardware trigger run appears to wait, confirm the physical trigger signal,
slope, delay, and timeout. Missing trigger edges can make the run wait or re-arm
according to the configured timeout behavior.
