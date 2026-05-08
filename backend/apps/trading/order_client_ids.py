"""Client order id builders for broker order idempotency."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from apps.trading.enums import Direction


@dataclass(frozen=True, slots=True)
class TradingOrderClientIdFactory:
    """Build stable OANDA client order ids for trading task order submissions."""

    prefix: str = "af"
    max_length: int = 128

    def open_position_id(
        self,
        *,
        task_id: Any,
        execution_id: Any,
        instrument: str,
        units: int,
        direction: Direction,
        layer_index: int | None,
        retracement_count: int | None,
        tick_timestamp: datetime | None,
        planned_exit_price: Decimal | None,
        stop_loss: Decimal | None,
    ) -> str:
        """Return a deterministic id for one strategy open-position intent."""
        raw = "|".join(
            [
                str(task_id),
                str(execution_id),
                instrument,
                str(units),
                direction.value,
                str(layer_index if layer_index is not None else ""),
                str(retracement_count if retracement_count is not None else ""),
                tick_timestamp.isoformat() if tick_timestamp is not None else "",
                str(planned_exit_price if planned_exit_price is not None else ""),
                str(stop_loss if stop_loss is not None else ""),
            ]
        )
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:40]
        label = self._safe_label(f"{instrument}-{direction.value}")
        value = f"{self.prefix}-{label}-{digest}"
        return value[: self.max_length]

    def _safe_label(self, value: str) -> str:
        safe = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-")
        return safe[:32] or "order"
