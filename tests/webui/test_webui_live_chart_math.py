from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
MATH_MODULE = REPO_ROOT / "src" / "meters_tool_webui" / "static" / "live_chart_math.js"
NODE = shutil.which("node")


@pytest.mark.skipif(NODE is None, reason="Node.js is required for live chart math module tests")
def test_live_chart_math_contracts():
    script = r'''
import assert from "node:assert/strict";
const [mathUrl] = process.argv.slice(1);
for (const name of ["document", "window", "navigator", "localStorage", "fetch", "FormData"]) {
  Object.defineProperty(globalThis, name, { configurable: true, get() { throw new Error(name); } });
}
const { liveChartScaleFor, clamp } = await import(mathUrl);
const scale = (...args) => liveChartScaleFor(...args);
const assertNear = (actual, expected) => assert.ok(Math.abs(actual - expected) < 1e-12);

const autoDeviation = scale([10, 10.2, 9.7], 10, "auto-deviation", null, false, null);
assert.equal(autoDeviation.mode, "auto-deviation");
assert.equal(autoDeviation.center, 10);
assertNear(autoDeviation.gridStepValue, 0.075);

const autoDeviationFloor = scale([10, 10], 10, "auto-deviation", null, false, null);
assertNear(autoDeviationFloor.gridStepValue, 1e-8);

const autoAbsolute = scale([2, 10], 0, "auto-absolute", null, false, null);
assert.equal(autoAbsolute.mode, "auto-absolute");
assert.equal(autoAbsolute.min, 2);
assert.equal(autoAbsolute.max, 10);
assert.equal(autoAbsolute.center, 6);
assertNear(autoAbsolute.gridStepValue, 0.88);

const autoAbsoluteFallback = scale([5, 5], 0, "auto-absolute", null, false, null);
assert.equal(autoAbsoluteFallback.min, 5);
assert.equal(autoAbsoluteFallback.max, 5);
assert.equal(autoAbsoluteFallback.center, 5);
assertNear(autoAbsoluteFallback.gridStepValue, 5e-9);

const manualSpan = scale([10], 10, "manual-span", 2, false, null);
assert.equal(manualSpan.mode, "manual-span");
assert.equal(manualSpan.center, 10);
assert.equal(manualSpan.span, 2);
assertNear(manualSpan.gridStepValue, 0.4);

const invalidManualSpan = scale([10, 10.2], 10, "manual-span", -1, false, null);
assert.equal(invalidManualSpan.mode, "manual-span-invalid");
assert.equal(invalidManualSpan.center, 10);
assertNear(invalidManualSpan.gridStepValue, 0.05);

const invalidManualInput = scale([10, 10.2], 10, "manual-span", 2, true, null);
assert.equal(invalidManualInput.mode, "manual-span-invalid");
assert.equal(invalidManualInput.center, 10);
assert.equal(invalidManualInput.span, 2);
assertNear(invalidManualInput.gridStepValue, 0.4);

const rangeStep = scale([10], 10, "range-step", null, false, 1);
assert.equal(rangeStep.mode, "range-step");
assert.equal(rangeStep.center, 10);
assert.equal(rangeStep.span, 1);
assertNear(rangeStep.gridStepValue, 0.2);

const invalidRangeStep = scale([10, 10.2], 10, "range-step", null, false, null);
assert.equal(invalidRangeStep.mode, "auto-deviation");
assert.equal(invalidRangeStep.center, 10);
assertNear(invalidRangeStep.gridStepValue, 0.05);

assert.equal(clamp(-10, -5, 5), -5);
assert.equal(clamp(2, -5, 5), 2);
assert.equal(clamp(10, -5, 5), 5);
process.stdout.write(JSON.stringify({ ok: true }));
'''
    completed = subprocess.run(
        [NODE, "--input-type=module", "--eval", script, MATH_MODULE.resolve().as_uri()],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert completed.returncode == 0, (
        "Node live chart math contract failed\n"
        f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
    )
    assert completed.stdout == '{"ok":true}'
