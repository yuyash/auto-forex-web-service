"""SnowballNet chart projection for the strategy detail tab."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

import v20
from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from v20.errors import V20Timeout
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.request import Request

from apps.market.models import OandaAccounts
from apps.market.views.candles import (
    OandaCandleFetchError,
    _fetch_oanda_candles,
    _parse_candle_time,
    _parse_candles,
)
from apps.trading.models.metrics import Metrics
from apps.trading.models.trades import Trade
from apps.trading.services.strategy_data_common import (
    granularity_seconds,
    parse_datetime,
    string_or_none,
)


DEFAULT_GRANULARITY = "H1"
DEFAULT_SIDE_BARS = 250
MAX_SIDE_BARS = 2000
OANDA_CANDLE_MAX_BATCH = 5000


class OandaCandleUnavailable(APIException):
    """Raised when OANDA candles cannot be fetched for the strategy chart."""

    status_code = 502
    default_detail = "Failed to fetch candles from OANDA."
    default_code = "oanda_candles_unavailable"


PRICE_LINE_SPECS = (
    ("average_price", "Average entry", "#2563eb", "snowballNet.chart.averagePrice"),
    ("target_price", "Take profit", "#16a34a", "snowballNet.chart.takeProfit"),
    ("next_add_price", "Next add", "#dc2626", "snowballNet.chart.nextAdd"),
)

OSCILLATOR_LINE_SPECS = (
    (
        "pips_from_average",
        "Pips from average",
        "#7c3aed",
        "snowballNet.chart.pipsFromAverage",
    ),
    ("margin_ratio_pct", "Margin %", "#ea580c", "snowballNet.chart.marginRatio"),
)


@dataclass(frozen=True, slots=True)
class NetChartWindow:
    granularity: str
    granularity_seconds: int
    center: datetime
    since: datetime
    until: datetime
    follow: bool
    merge_markers: bool


def build_snowball_net_chart(
    *,
    request: Request,
    task: Any,
    task_type_label: str,
    execution_id: Any,
    strategy_type: str,
    strategy_state: dict[str, Any],
    last_tick_timestamp: str | None,
) -> dict[str, Any]:
    """Build the chart payload consumed by the SnowballNet strategy tab."""
    current_timestamp = _resolve_current_timestamp(strategy_state, last_tick_timestamp)
    window = _window_from_request(request, last_tick_timestamp=current_timestamp)
    instrument = str(getattr(task, "instrument", "") or "")
    account = _resolve_oanda_account(request=request, task=task)

    return {
        "execution_id": string_or_none(execution_id),
        "strategy_type": strategy_type,
        "instrument": instrument,
        "window": {
            "granularity": window.granularity,
            "granularity_seconds": window.granularity_seconds,
            "center": window.center.isoformat(),
            "since": window.since.isoformat(),
            "until": window.until.isoformat(),
            "follow": window.follow,
            "merge_markers": window.merge_markers,
        },
        "current": _current_state(strategy_state, current_timestamp),
        "candles": _load_candles(
            account=account,
            instrument=instrument,
            since=window.since,
            until=window.until,
            granularity=window.granularity,
        ),
        "price_lines": _load_price_lines(
            task=task,
            task_type_label=task_type_label,
            execution_id=execution_id,
            since=window.since,
            until=window.until,
            granularity_seconds=window.granularity_seconds,
        ),
        "oscillator_lines": _load_oscillator_lines(
            task=task,
            task_type_label=task_type_label,
            execution_id=execution_id,
            since=window.since,
            until=window.until,
            granularity_seconds=window.granularity_seconds,
        ),
        "markers": _load_markers(
            task=task,
            task_type_label=task_type_label,
            execution_id=execution_id,
            since=window.since,
            until=window.until,
            granularity_seconds=window.granularity_seconds,
            merge=window.merge_markers,
        ),
    }


def _window_from_request(
    request: Request,
    *,
    last_tick_timestamp: str | None,
) -> NetChartWindow:
    params = request.query_params
    granularity = _normalise_chart_granularity(params.get("granularity") or DEFAULT_GRANULARITY)
    seconds = granularity_seconds(granularity)
    if seconds is None:
        raise ValidationError("granularity must be M1, M5, M15, M30, H1, H4, or D.")

    follow = _parse_bool(params.get("follow"), True)
    merge_markers = _parse_bool(params.get("merge_markers"), True)
    center = (
        parse_datetime(params.get("center"))
        or parse_datetime(last_tick_timestamp)
        or timezone.now()
    )
    if center.tzinfo is None:
        center = center.replace(tzinfo=UTC)

    since = parse_datetime(params.get("since"))
    until = parse_datetime(params.get("until"))
    if since is None or until is None:
        before_bars = _clamped_int(params.get("before_bars"), DEFAULT_SIDE_BARS)
        after_bars = _clamped_int(params.get("after_bars"), DEFAULT_SIDE_BARS)
        since = center - timedelta(seconds=seconds * before_bars)
        until = center + timedelta(seconds=seconds * after_bars)
    if since > until:
        raise ValidationError("since must be earlier than until.")
    return NetChartWindow(
        granularity=granularity,
        granularity_seconds=seconds,
        center=center,
        since=since,
        until=until,
        follow=follow,
        merge_markers=merge_markers,
    )


def _normalise_chart_granularity(value: Any) -> str:
    raw = str(value or DEFAULT_GRANULARITY).strip().upper()
    if raw in {"", "RAW", "TICK", "1"}:
        return "M1"
    if raw.isdigit():
        raw = f"M{raw}"
    if raw in {"M60", "H1"}:
        return "H1"
    if raw in {"M240", "H4"}:
        return "H4"
    if raw in {"M1", "M5", "M15", "M30", "D"}:
        return raw
    raise ValidationError("granularity must be M1, M5, M15, M30, H1, H4, or D.")


def _resolve_oanda_account(*, request: Request, task: Any) -> OandaAccounts:
    task_account = getattr(task, "oanda_account", None)
    if task_account is not None:
        return task_account

    user_id = getattr(getattr(request, "user", None), "pk", None) or getattr(task, "user_id", None)
    if user_id is None:
        raise ValidationError("OANDA account is required to fetch candles.")

    account_ref = request.query_params.get("account_id")
    accounts = OandaAccounts.objects.filter(user_id=user_id, is_active=True)
    if account_ref:
        account_query = Q(account_id=str(account_ref))
        try:
            account_query |= Q(pk=int(account_ref))
        except (TypeError, ValueError):
            pass
        account = accounts.filter(account_query).first()
        if account is None:
            raise ValidationError("OANDA account not found.")
        return account

    account = accounts.filter(is_default=True).first() or accounts.first()
    if account is None:
        raise ValidationError("No OANDA account found. Please configure an account first.")
    return account


def _load_candles(
    *,
    account: OandaAccounts,
    instrument: str,
    since: datetime,
    until: datetime,
    granularity: str,
) -> list[dict[str, Any]]:
    if not instrument:
        return []
    fetch_until = min(until, timezone.now())
    if since >= fetch_until:
        return []

    api_context = v20.Context(
        hostname=account.api_hostname,
        token=account.get_api_token(),
        application="auto-forex-trading",
        poll_timeout=int(getattr(settings, "OANDA_REST_TIMEOUT", 10)),
    )
    try:
        raw_candles = _fetch_oanda_candles_for_window(
            api_context=api_context,
            instrument=instrument,
            granularity=granularity,
            since=since,
            until=fetch_until,
        )
    except OandaCandleFetchError as exc:
        raise OandaCandleUnavailable("Failed to fetch candles from OANDA.") from exc
    except V20Timeout as exc:
        raise OandaCandleUnavailable("OANDA candle request timed out.") from exc
    return _parse_candles(raw_candles)


def _fetch_oanda_candles_for_window(
    *,
    api_context: v20.Context,
    instrument: str,
    granularity: str,
    since: datetime,
    until: datetime,
) -> list[Any]:
    step = granularity_seconds(granularity) or 3600
    estimated = int((until - since).total_seconds() / step) + 2
    if estimated <= OANDA_CANDLE_MAX_BATCH:
        return _fetch_oanda_candles(
            api_context,
            instrument,
            granularity=granularity,
            fromTime=_format_oanda_time(since),
            toTime=_format_oanda_time(until),
        )

    candles: list[Any] = []
    current_from = since
    while current_from < until:
        current_to = datetime.fromtimestamp(
            min(
                current_from.timestamp() + OANDA_CANDLE_MAX_BATCH * step,
                until.timestamp(),
            ),
            tz=UTC,
        )
        batch = _fetch_oanda_candles(
            api_context,
            instrument,
            granularity=granularity,
            fromTime=_format_oanda_time(current_from),
            toTime=_format_oanda_time(current_to),
        )
        if not batch:
            break
        candles.extend(batch)

        last_dt = _parse_candle_time(batch[-1])
        if last_dt is None:
            break
        next_from = datetime.fromtimestamp(last_dt.timestamp() + step, tz=UTC)
        if next_from <= current_from:
            break
        current_from = next_from
    return candles


def _format_oanda_time(value: datetime) -> str:
    aware = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return aware.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _load_price_lines(
    *,
    task: Any,
    task_type_label: str,
    execution_id: Any,
    since: datetime,
    until: datetime,
    granularity_seconds: int,
) -> list[dict[str, Any]]:
    bucketed = _load_metric_buckets(
        task=task,
        task_type_label=task_type_label,
        execution_id=execution_id,
        since=since,
        until=until,
        granularity_seconds=granularity_seconds,
    )
    return [
        _series_from_buckets(
            buckets=bucketed,
            key=key,
            label=label,
            color=color,
            label_key=label_key,
        )
        for key, label, color, label_key in PRICE_LINE_SPECS
    ]


def _load_oscillator_lines(
    *,
    task: Any,
    task_type_label: str,
    execution_id: Any,
    since: datetime,
    until: datetime,
    granularity_seconds: int,
) -> list[dict[str, Any]]:
    bucketed = _load_metric_buckets(
        task=task,
        task_type_label=task_type_label,
        execution_id=execution_id,
        since=since,
        until=until,
        granularity_seconds=granularity_seconds,
    )
    return [
        _series_from_buckets(
            buckets=bucketed,
            key=key,
            label=label,
            color=color,
            label_key=label_key,
        )
        for key, label, color, label_key in OSCILLATOR_LINE_SPECS
    ]


def _load_metric_buckets(
    *,
    task: Any,
    task_type_label: str,
    execution_id: Any,
    since: datetime,
    until: datetime,
    granularity_seconds: int,
) -> dict[int, dict[str, Decimal]]:
    rows = (
        Metrics.objects.filter(
            task_type=task_type_label,
            task_id=task.pk,
            execution_id=execution_id,
            timestamp__gte=since,
            timestamp__lte=until,
        )
        .order_by("timestamp")
        .values_list("timestamp", "metrics")
    )
    buckets: dict[int, dict[str, Decimal]] = {}
    for timestamp, metrics in rows:
        if not isinstance(metrics, dict):
            continue
        bucket = _bucket(timestamp, granularity_seconds)
        current = buckets.setdefault(bucket, {})
        current.update(_extract_net_metrics(metrics))
    return buckets


def _extract_net_metrics(metrics: dict[str, Any]) -> dict[str, Decimal]:
    extracted = {
        "average_price": _decimal(metrics.get("snowball_net_average_price")),
        "target_price": _decimal(metrics.get("snowball_net_target_price")),
        "next_add_price": _decimal(metrics.get("snowball_net_next_add_price")),
        "pips_from_average": _decimal(metrics.get("snowball_net_pips_from_average")),
        "margin_ratio_pct": _decimal(metrics.get("snowball_net_margin_ratio_pct")),
    }
    if extracted["margin_ratio_pct"] is None:
        margin_ratio = _decimal(metrics.get("margin_ratio"))
        if margin_ratio is not None:
            extracted["margin_ratio_pct"] = margin_ratio * Decimal("100")
    return {key: value for key, value in extracted.items() if value is not None}


def _series_from_buckets(
    *,
    buckets: dict[int, dict[str, Decimal]],
    key: str,
    label: str,
    color: str,
    label_key: str,
) -> dict[str, Any]:
    return {
        "id": key,
        "label": label,
        "label_key": label_key,
        "color": color,
        "points": [
            {"time": bucket, "value": float(values[key])}
            for bucket, values in sorted(buckets.items())
            if key in values
        ],
    }


def _load_markers(
    *,
    task: Any,
    task_type_label: str,
    execution_id: Any,
    since: datetime,
    until: datetime,
    granularity_seconds: int,
    merge: bool,
) -> list[dict[str, Any]]:
    trades = (
        Trade.objects.filter(
            task_type=task_type_label,
            task_id=task.pk,
            execution_id=execution_id,
            timestamp__gte=since,
            timestamp__lte=until,
        )
        .order_by("timestamp", "sequence_number")
        .values(
            "id",
            "timestamp",
            "direction",
            "units",
            "price",
            "execution_method",
            "description",
            "position_id",
            "sequence_number",
        )
    )
    if not merge:
        return [_marker_from_trade(trade, granularity_seconds=None) for trade in trades]

    grouped: dict[tuple[int, str], list[dict[str, Any]]] = defaultdict(list)
    for trade in trades:
        action = _trade_action(str(trade.get("execution_method") or ""))
        timestamp = trade.get("timestamp")
        if not isinstance(timestamp, datetime):
            continue
        grouped[(_bucket(timestamp, granularity_seconds), action)].append(trade)

    markers = []
    for (bucket, action), items in sorted(grouped.items()):
        total_units = sum(abs(int(item.get("units") or 0)) for item in items)
        last = items[-1]
        markers.append(
            {
                "id": f"merged:{bucket}:{action}",
                "time": bucket,
                "action": action,
                "direction": last.get("direction"),
                "units": total_units,
                "price": float(last["price"]) if last.get("price") is not None else None,
                "count": len(items),
                "label": f"{action} x{len(items)}",
                "description": f"{len(items)} {action} trade(s), {total_units} units",
                "trade_ids": [str(item["id"]) for item in items],
            }
        )
    return markers


def _marker_from_trade(
    trade: dict[str, Any],
    *,
    granularity_seconds: int | None,
) -> dict[str, Any]:
    timestamp = trade.get("timestamp")
    if not isinstance(timestamp, datetime):
        time_value = 0
    elif granularity_seconds is not None:
        time_value = _bucket(timestamp, granularity_seconds)
    else:
        time_value = int(timestamp.timestamp())
    action = _trade_action(str(trade.get("execution_method") or ""))
    return {
        "id": str(trade["id"]),
        "time": time_value,
        "timestamp": timestamp.isoformat() if isinstance(timestamp, datetime) else None,
        "action": action,
        "direction": trade.get("direction"),
        "units": abs(int(trade.get("units") or 0)),
        "price": float(trade["price"]) if trade.get("price") is not None else None,
        "count": 1,
        "label": action,
        "description": trade.get("description") or "",
        "trade_ids": [str(trade["id"])],
        "position_id": string_or_none(trade.get("position_id")),
    }


def _current_state(
    strategy_state: dict[str, Any], last_tick_timestamp: str | None
) -> dict[str, Any]:
    metrics = (
        strategy_state.get("metrics") if isinstance(strategy_state.get("metrics"), dict) else {}
    )
    return {
        "timestamp": last_tick_timestamp,
        "bid": strategy_state.get("last_bid"),
        "ask": strategy_state.get("last_ask"),
        "mid": strategy_state.get("last_mid"),
        "net_units": strategy_state.get("net_units"),
        "average_price": strategy_state.get("average_price"),
        "current_price": metrics.get("snowball_net_current_price"),
        "pips_from_average": metrics.get("snowball_net_pips_from_average"),
        "target_price": metrics.get("snowball_net_target_price"),
        "next_add_price": metrics.get("snowball_net_next_add_price"),
        "margin_ratio_pct": metrics.get("snowball_net_margin_ratio_pct"),
        "pending_action": strategy_state.get("pending_action") or {},
        "last_action": strategy_state.get("last_action") or {},
    }


def _resolve_current_timestamp(
    strategy_state: dict[str, Any], last_tick_timestamp: str | None
) -> str | None:
    state_timestamp = strategy_state.get("last_tick_timestamp")
    if state_timestamp:
        return str(state_timestamp)
    return last_tick_timestamp


def _trade_action(execution_method: str) -> str:
    return (
        "open" if execution_method in {"open_position", "initial_entry", "retracement"} else "close"
    )


def _bucket(timestamp: datetime, granularity_seconds: int) -> int:
    aware = timestamp if timestamp.tzinfo is not None else timestamp.replace(tzinfo=UTC)
    return int(aware.timestamp()) // granularity_seconds * granularity_seconds


def _decimal(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _parse_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _clamped_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(1, min(MAX_SIDE_BARS, parsed))
