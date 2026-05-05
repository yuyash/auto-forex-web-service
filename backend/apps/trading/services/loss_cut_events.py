"""Loss-cut event loader for chart overlays.

A loss-cut is a strategy-driven forced close that fires when the running
position moves too far into loss or breaches a margin-closeout safeguard.
Rendering these events as vertical reference lines on the metric and
strategy charts helps users correlate abrupt drops in balance/P&L or
spikes in margin ratio with the liquidation that caused them.

Loss-cut trades are already written by strategies into the ``trades``
table using the ``close_position`` execution method.  The strategy tags
them in one of two ways:

* SnowballNet: ``description`` contains ``"loss cut"`` and the parent
  strategy event carries ``close_reason='net_loss_cut'``.
* Snowball: entries are closed with ``close_reason='stop_loss'`` and the
  description text includes ``"stop_loss"``.

We match on ``description`` to keep the loader strategy-agnostic while
still filtering out take-profit and margin-reduce closes.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from django.db.models import Q

from apps.trading.models.trades import Trade


# Description fragments recorded by strategies when closing on a
# loss-protection rule.  Matching is case-insensitive so both
# ``"SnowballNet loss cut"`` (human readable) and the internal
# ``"loss_cut"`` tag are detected.
_LOSS_CUT_MARKERS: tuple[str, ...] = (
    "loss cut",
    "loss_cut",
    "stop_loss",
    "stop loss",
)


def load_loss_cut_events(
    *,
    task: Any,
    task_type_label: str,
    execution_id: Any,
    since: datetime | None = None,
    until: datetime | None = None,
) -> list[dict[str, Any]]:
    """Return a list of loss-cut markers, ordered by timestamp ascending.

    Each marker has the shape expected by the frontend chart overlays:

    ``{"id", "timestamp", "time" (unix seconds), "units", "direction",
      "price", "description", "position_id"}``
    """

    description_filter = Q()
    for token in _LOSS_CUT_MARKERS:
        description_filter |= Q(description__icontains=token)

    qs = Trade.objects.filter(
        task_type=task_type_label,
        task_id=task.pk,
        execution_id=execution_id,
        execution_method="close_position",
    ).filter(description_filter)

    if since is not None:
        qs = qs.filter(timestamp__gte=since)
    if until is not None:
        qs = qs.filter(timestamp__lte=until)

    qs = qs.order_by("timestamp", "sequence_number").values(
        "id",
        "timestamp",
        "direction",
        "units",
        "price",
        "description",
        "position_id",
    )

    results: list[dict[str, Any]] = []
    for row in qs:
        timestamp = row["timestamp"]
        if not isinstance(timestamp, datetime):
            continue
        results.append(
            {
                "id": str(row["id"]),
                "timestamp": timestamp.isoformat(),
                "time": int(timestamp.timestamp()),
                "units": abs(int(row["units"] or 0)),
                "direction": row.get("direction"),
                "price": float(row["price"]) if row.get("price") is not None else None,
                "description": row.get("description") or "",
                "position_id": str(row["position_id"]) if row.get("position_id") else None,
            }
        )
    return results
