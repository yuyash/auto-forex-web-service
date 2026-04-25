"""Snowball strategy compatibility checks for resumed executions."""

from __future__ import annotations

from typing import Any

from apps.trading.services.resume_config import ResumeConfigurationError


def validate_resume_parameter_compatibility(
    *,
    previous_params: dict[str, Any],
    current_params: dict[str, Any],
) -> None:
    """Validate snowball parameters that must remain state-compatible on resume."""
    previous_r_max = _to_int(previous_params.get("r_max"))
    current_r_max = _to_int(current_params.get("r_max"))
    if previous_r_max is not None and current_r_max is not None and current_r_max < previous_r_max:
        raise ResumeConfigurationError(
            "Cannot resume a snowball execution after decreasing r_max. "
            "Increase it or restart the task so existing layers are rebuilt from scratch.",
            code="resume_snowball_r_max_decreased",
            blocked_fields=["parameters.r_max"],
        )


def _to_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
