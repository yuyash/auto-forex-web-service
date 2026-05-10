"""Task instrument metadata and pip-size context."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal

from apps.trading.utils import Instrument

PipSizeSource = Literal["instrument_default", "task_override"]


def _plain_decimal(value: Decimal) -> str:
    if value.is_zero():
        return "0"
    text = format(value.normalize(), "f")
    if "." not in text:
        return text
    return text.rstrip("0").rstrip(".")


@dataclass(frozen=True, slots=True)
class TaskInstrumentContext:
    """Instrument metadata and pip-size diagnostics for task API payloads."""

    instrument: str
    instrument_metadata: dict[str, str | bool]
    configured_pip_size: str
    default_pip_size: str
    effective_pip_size: str
    pip_size_source: PipSizeSource
    pip_size_matches_instrument: bool

    def as_dict(self) -> dict[str, Any]:
        """Serialize context as JSON-friendly primitives."""
        return {
            "instrument": self.instrument,
            "instrument_metadata": self.instrument_metadata,
            "configured_pip_size": self.configured_pip_size,
            "default_pip_size": self.default_pip_size,
            "effective_pip_size": self.effective_pip_size,
            "pip_size_source": self.pip_size_source,
            "pip_size_matches_instrument": self.pip_size_matches_instrument,
        }


class TaskInstrumentContextBuilder:
    """Build task-level instrument context without touching broker APIs."""

    def build(self, task: Any) -> TaskInstrumentContext:
        """Return instrument metadata and pip-size diagnostics for a task."""
        instrument_name = str(getattr(task, "instrument", "") or "").strip()
        instrument = Instrument(instrument_name)
        default_pip_size = instrument.pip_size
        configured_pip_size = _decimal_or_none(getattr(task, "pip_size", None))
        effective_pip_size = configured_pip_size or default_pip_size
        matches_default = effective_pip_size == default_pip_size
        pip_size_source: PipSizeSource = (
            "instrument_default" if matches_default else "task_override"
        )

        return TaskInstrumentContext(
            instrument=instrument.normalized_name,
            instrument_metadata=instrument.as_metadata(),
            configured_pip_size=(
                _plain_decimal(configured_pip_size) if configured_pip_size is not None else ""
            ),
            default_pip_size=_plain_decimal(default_pip_size),
            effective_pip_size=_plain_decimal(effective_pip_size),
            pip_size_source=pip_size_source,
            pip_size_matches_instrument=matches_default,
        )


def _decimal_or_none(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    return Decimal(str(value))


TASK_INSTRUMENT_CONTEXT = TaskInstrumentContextBuilder()
