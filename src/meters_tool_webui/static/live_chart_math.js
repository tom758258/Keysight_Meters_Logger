const LIVE_CHART_VISIBLE_GRID_LIMIT = 4;
export const LIVE_CHART_GRID_LINE_COUNT_PER_SIDE = 5;

export function liveChartScaleFor(
  values,
  baseline,
  mode,
  manualSpan,
  manualSpanInputInvalid,
  rangeStepSpan
) {
  if (mode === "auto-absolute") {
    return chartScaleForAutoAbsolute(values);
  }
  if (mode === "range-step") {
    return (
      chartScaleForRangeStep(baseline, rangeStepSpan) ||
      chartScaleForAutoDeviation(values, baseline)
    );
  }
  if (mode === "manual-span") {
    const manualScale = chartScaleForManualSpan(baseline, manualSpan);
    if (manualSpanInputInvalid) {
      return {
        ...(manualScale || chartScaleForAutoDeviation(values, baseline)),
        mode: "manual-span-invalid",
      };
    }
    if (manualScale) {
      return manualScale;
    }
    return {
      ...chartScaleForAutoDeviation(values, baseline),
      mode: "manual-span-invalid",
    };
  }
  return chartScaleForAutoDeviation(values, baseline);
}

function chartScaleForAutoDeviation(values, baseline) {
  const deviations = values.map((value) => value - baseline);
  const maxAbsDeviation = Math.max(...deviations.map((value) => Math.abs(value)));
  const gridStepValue = Math.max(
    maxAbsDeviation / LIVE_CHART_VISIBLE_GRID_LIMIT,
    minimumGridValueFor(baseline)
  );
  return {
    mode: "auto-deviation",
    center: baseline,
    gridStepValue,
  };
}

function chartScaleForAutoAbsolute(values) {
  const min = Math.min(...values);
  const max = Math.max(...values);
  const center = (min + max) / 2;
  const halfRange = (max - min) / 2;
  const paddedHalfRange = Math.max(
    halfRange * 1.1,
    minimumGridValueFor(center) * LIVE_CHART_GRID_LINE_COUNT_PER_SIDE
  );
  return {
    mode: "auto-absolute",
    center,
    gridStepValue: paddedHalfRange / LIVE_CHART_GRID_LINE_COUNT_PER_SIDE,
    min,
    max,
  };
}

function chartScaleForManualSpan(baseline, span) {
  if (!Number.isFinite(span) || span <= 0) {
    return null;
  }
  return {
    mode: "manual-span",
    center: baseline,
    gridStepValue: span / LIVE_CHART_GRID_LINE_COUNT_PER_SIDE,
    span,
  };
}

function chartScaleForRangeStep(baseline, span) {
  if (!Number.isFinite(span) || span <= 0) {
    return null;
  }
  return {
    mode: "range-step",
    center: baseline,
    gridStepValue: span / LIVE_CHART_GRID_LINE_COUNT_PER_SIDE,
    span,
  };
}

function minimumGridValueFor(value) {
  return Math.max(Math.abs(value), 1) * 1e-9;
}

export function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}
