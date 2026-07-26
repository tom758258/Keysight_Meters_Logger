# Common Orchestrator Workflows

Schema version: `2`

Compatibility policy: `v2-only`

This document defines the abstract cross-instrument lifecycle for agents that
drive Worker subprocesses. Instrument-specific commands, mode/model context,
resources, trigger semantics, and artifacts belong in instrument-specific
workflow documents.

## Lifecycle

1. Build a plan or dry-run request when the Worker supports one.
2. Start the Worker subprocess in machine-output mode.
3. Read stdout as JSONL and wait for a `ready` event, or poll
   `GET /status` until a valid status object is reachable.
4. Correlate stdout events, status responses, and artifacts with `run_id` when
   the Worker creates a runtime session.
5. Build the schema-2 `context` required by the Worker-specific contract.
6. Use Worker-specific `POST /command` requests only after the control plane is
   ready. Parse the Common command response envelope and correlate echoed
   `command` and `job_id` identities.
7. Use `GET /status` for non-mutating health and progress checks.
8. Use `POST /stop` or the Worker-specific stop client for cooperative
   cleanup.
9. Read structured output and artifacts for pass/fail decisions. Human text is
   diagnostic output only.

## Failure Handling

Treat a missing `ready` event, unreachable status endpoint, malformed JSON,
non-zero process exit code, missing final summary, or final `ok: false` summary
as failed or incomplete until the instrument-specific contract says otherwise.

`GET /status` must be non-mutating. Orchestrators can poll it for readiness,
but should avoid adding extra request loops to instrument I/O paths.

## Live Resource Safety

Live runs should use an explicit resource selected by the operator or by a
previous explicit discovery step. Cross-instrument orchestrators should not
scan, guess, or rotate through resource strings inside an active workflow
unless the Worker-specific contract explicitly allows it.

## Cleanup

Prefer cooperative stop before terminating a Worker process. If a process has
already exited, client-side cleanup may report that the endpoint is no longer
listening; instrument-specific contracts define whether that is a successful
cleanup result.
