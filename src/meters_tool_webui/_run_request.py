from __future__ import annotations

from typing import Any


def normalize_run_request_values(request: Any) -> dict[str, Any]:
    raw = _model_dict(request)
    raw["resource"] = str(raw["resource"]).strip()
    if not raw["resource"]:
        raise ValueError("resource is required")
    if raw.get("csv") is not None:
        raw["csv"] = str(raw["csv"]).strip() or None
    raw_model = raw.get("instrument_model")
    if raw_model is not None:
        raw["instrument_model"] = str(raw_model).strip() or None
    if raw.get("trigger_mode") is not None:
        raw["trigger_mode"] = str(raw["trigger_mode"]).strip().lower()
    raw["hw_trigger_slope"] = str(raw["hw_trigger_slope"]).strip().lower()
    if raw["hw_trigger_slope"] not in {"pos", "neg"}:
        raise ValueError("hw_trigger_slope must be 'pos' or 'neg'")
    if raw.get("vm_comp_slope") is not None:
        raw["vm_comp_slope"] = str(raw["vm_comp_slope"]).strip().lower() or None
        if raw["vm_comp_slope"] is not None and raw["vm_comp_slope"] not in {
            "pos",
            "neg",
        }:
            raise ValueError("vm_comp_slope must be 'pos' or 'neg'")
    raw["dcv_input_impedance"] = _parse_dcv_input_impedance(
        raw["dcv_input_impedance"]
    )

    # Normalize legacy boolean payloads while keeping Core's semantic strings.
    auto_zero_val = raw.get("auto_zero")
    if isinstance(auto_zero_val, bool):
        raw["auto_zero"] = "on" if auto_zero_val else "off"
    elif isinstance(auto_zero_val, str):
        normalized_val = auto_zero_val.strip().lower()
        if normalized_val in ("true", "on"):
            raw["auto_zero"] = "on"
        elif normalized_val in ("false", "off"):
            raw["auto_zero"] = "off"
        elif normalized_val == "once":
            raw["auto_zero"] = "once"
        else:
            raise ValueError("auto_zero must be 'on', 'off', 'once', or a boolean")
    else:
        raw["auto_zero"] = "on"

    return raw


def _model_dict(model: Any) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def _parse_dcv_input_impedance(value: str) -> str:
    normalized = str(value).strip().lower()
    if normalized in {"default", "10m", "auto"}:
        return normalized
    raise ValueError("dcv_input_impedance must be 'default', '10m', or 'auto'")
