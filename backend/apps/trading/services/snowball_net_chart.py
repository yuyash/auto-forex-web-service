"""SnowballNet chart projection for the strategy detail tab."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, cast

import v20
from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from v20.errors import V20Timeout
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.request import Request

from apps.market.models import OandaAccounts
from apps.market.services.candles import load_market_candles
from apps.market.views.candles import (
    OandaCandleFetchError,
    _fetch_oanda_candles,
    _parse_candle_time,
    _parse_candles,
)
from apps.trading.models.metrics import Metrics
from apps.trading.models.positions import Position
from apps.trading.models.trades import Trade
from apps.trading.services.strategy_data_common import (
    granularity_seconds,
    parse_datetime,
    string_or_none,
)
from apps.trading.strategies.snowball_net.config import SnowballNetConfig
from apps.trading.utils import pip_size_for_instrument, quote_to_account_rate


DEFAULT_GRANULARITY = "M1"
DEFAULT_SIDE_BARS = 24 * 60
MAX_CHART_RANGE_BARS = 14 * 24 * 60
MAX_SIDE_BARS = 2000
OANDA_CANDLE_MAX_BATCH = 5000


class OandaCandleUnavailable(APIException):
    """Raised when OANDA candles cannot be fetched for the strategy chart."""

    status_code = 502
    default_detail = "Failed to fetch candles from OANDA."
    default_code = "oanda_candles_unavailable"


PRICE_LINE_SPECS = (
    (
        "average_price",
        "Average order price",
        "#2563eb",
        "snowballNet.chart.averagePrice",
    ),
    ("target_price", "Exit price", "#16a34a", "snowballNet.chart.takeProfit"),
)

CURRENT_PRICE_LINE_SPEC = (
    "current_price",
    "Current price",
    "#475569",
    "snowballNet.chart.currentPrice",
)

NEXT_ADD_LINE_SPEC = (
    "next_add_price",
    "Next add price",
    "#dc2626",
    "snowballNet.chart.nextAdd",
)

OSCILLATOR_LINE_SPECS = (
    ("net_units", "Net units", "#0288d1", "snowballNet.chart.netUnits"),
    (
        "pips_from_average",
        "Pips from average order price",
        "#7c3aed",
        "snowballNet.chart.pipsFromAverage",
    ),
    (
        "margin_ratio_pct",
        "Margin closeout ratio",
        "#ea580c",
        "snowballNet.chart.marginRatio",
    ),
)

PNL_LINE_SPECS = (
    ("realized_pnl", "Realized PnL", "#2e7d32", "snowballNet.chart.realizedPnl"),
    (
        "unrealized_pnl",
        "Unrealized PnL",
        "#7b1fa2",
        "snowballNet.chart.unrealizedPnl",
    ),
)

LOSS_CUT_THRESHOLD_LINE_SPEC = (
    "loss_cut_threshold_pips",
    "Loss cut threshold",
    "#dc2626",
    "snowballNet.chart.lossCutThreshold",
)

MARGIN_THRESHOLD_LINE_SPECS = (
    (
        "margin_reduce_threshold_pct",
        "Margin reduce threshold",
        "#f97316",
        "snowballNet.chart.marginReduceThreshold",
    ),
    (
        "margin_reduce_target_pct",
        "Margin reduce target",
        "#14b8a6",
        "snowballNet.chart.marginReduceTarget",
    ),
    (
        "emergency_threshold_pct",
        "Emergency stop threshold",
        "#b91c1c",
        "snowballNet.chart.emergencyThreshold",
    ),
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
    strategy_data_until = _strategy_data_until(window)
    instrument = str(getattr(task, "instrument", "") or "")
    pnl_currency = _resolve_pnl_currency(task=task, instrument=instrument)
    quote_currency = _quote_currency(instrument)
    metric_buckets = _load_metric_buckets(
        task=task,
        task_type_label=task_type_label,
        execution_id=execution_id,
        since=window.since,
        until=strategy_data_until,
        granularity_seconds=window.granularity_seconds,
    )

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
        "current": _current_state(
            strategy_state,
            current_timestamp,
            task=task,
            instrument=instrument,
            pnl_currency=pnl_currency,
            quote_currency=quote_currency,
        ),
        "candles": _load_candles(
            request=request,
            task=task,
            task_type_label=task_type_label,
            instrument=instrument,
            since=window.since,
            until=window.until,
            granularity=window.granularity,
        ),
        "price_lines": _price_lines_from_buckets(
            task=task,
            buckets=metric_buckets,
        ),
        "oscillator_lines": _oscillator_lines_from_buckets(
            task=task,
            since=window.since,
            until=strategy_data_until,
            buckets=metric_buckets,
        ),
        "markers": _load_markers(
            task=task,
            task_type_label=task_type_label,
            execution_id=execution_id,
            since=window.since,
            until=strategy_data_until,
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
    _validate_chart_window_range(
        granularity=granularity,
        granularity_seconds=seconds,
        since=since,
        until=until,
    )
    return NetChartWindow(
        granularity=granularity,
        granularity_seconds=seconds,
        center=center,
        since=since,
        until=until,
        follow=follow,
        merge_markers=merge_markers,
    )


def _strategy_data_until(window: NetChartWindow) -> datetime:
    if not window.follow:
        return window.until
    if window.center <= window.since:
        return window.since
    return min(window.center, window.until)


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


def _validate_chart_window_range(
    *,
    granularity: str,
    granularity_seconds: int,
    since: datetime,
    until: datetime,
) -> None:
    max_seconds = granularity_seconds * MAX_CHART_RANGE_BARS
    if (until - since).total_seconds() <= max_seconds:
        return
    raise ValidationError(
        f"granularity {granularity} supports ranges up to {_format_duration_seconds(max_seconds)}."
    )


def _format_duration_seconds(seconds: int) -> str:
    if seconds % 86400 == 0:
        days = seconds // 86400
        return f"{days} day{'s' if days != 1 else ''}"
    if seconds % 3600 == 0:
        hours = seconds // 3600
        return f"{hours} hour{'s' if hours != 1 else ''}"
    minutes = seconds // 60
    return f"{minutes} minute{'s' if minutes != 1 else ''}"


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
    request: Request,
    task: Any,
    task_type_label: str,
    instrument: str,
    since: datetime,
    until: datetime,
    granularity: str,
) -> list[dict[str, Any]]:
    if not instrument:
        return []
    if task_type_label == "backtest":
        stored_candles = load_market_candles(
            instrument=instrument,
            granularity=granularity,
            since=since,
            until=until,
        )
        if stored_candles:
            return stored_candles

    account = _resolve_oanda_account(request=request, task=task)
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
    return _price_lines_from_buckets(task=task, buckets=bucketed)


def _price_lines_from_buckets(
    *,
    task: Any,
    buckets: dict[int, dict[str, Decimal]],
) -> list[dict[str, Any]]:
    lines = [
        _series_from_buckets(
            buckets=buckets,
            key=key,
            label=label,
            color=color,
            label_key=label_key,
        )
        for key, label, color, label_key in PRICE_LINE_SPECS
    ]
    key, label, color, label_key = CURRENT_PRICE_LINE_SPEC
    lines.append(
        _series_from_buckets(
            buckets=buckets,
            key=key,
            label=label,
            color=color,
            label_key=label_key,
            line_style="dashed",
        )
    )
    lines.extend(_next_add_price_lines(task=task, buckets=buckets))
    return lines


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
    return _oscillator_lines_from_buckets(
        task=task,
        since=since,
        until=until,
        buckets=bucketed,
    )


def _oscillator_lines_from_buckets(
    *,
    task: Any,
    since: datetime,
    until: datetime,
    buckets: dict[int, dict[str, Decimal]],
) -> list[dict[str, Any]]:
    lines = [
        _series_from_buckets(
            buckets=buckets,
            key=key,
            label=label,
            color=color,
            label_key=label_key,
        )
        for key, label, color, label_key in OSCILLATOR_LINE_SPECS
    ]
    lines.extend(
        _series_from_buckets(
            buckets=buckets,
            key=key,
            label=label,
            color=color,
            label_key=label_key,
        )
        for key, label, color, label_key in PNL_LINE_SPECS
    )
    lines.extend(_loss_cut_threshold_lines(task=task, since=since, until=until))
    lines.extend(_margin_threshold_lines(task=task, since=since, until=until))
    return lines


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
        current.update(
            _extract_net_metrics(
                metrics,
                task=task,
                instrument=str(getattr(task, "instrument", "") or ""),
            )
        )
    _apply_position_pnl_buckets(
        buckets=buckets,
        task=task,
        task_type_label=task_type_label,
        execution_id=execution_id,
        since=since,
        until=until,
    )
    return buckets


def _extract_net_metrics(
    metrics: dict[str, Any], *, task: Any, instrument: str
) -> dict[str, Decimal]:
    extracted = {
        "net_units": _decimal(metrics.get("snowball_net_net_units")),
        "average_price": _decimal(metrics.get("snowball_net_average_price")),
        "current_price": _decimal(metrics.get("snowball_net_current_price")),
        "target_price": _decimal(metrics.get("snowball_net_target_price")),
        "next_add_price": _decimal(metrics.get("snowball_net_next_add_price")),
        "theoretical_next_add_price": _decimal(
            metrics.get("snowball_net_theoretical_next_add_price")
        ),
        "pips_from_average": _decimal(metrics.get("snowball_net_pips_from_average")),
        "loss_cut_threshold_pips": _decimal(metrics.get("snowball_net_loss_cut_threshold_pips")),
        "margin_ratio_pct": _decimal(metrics.get("snowball_net_margin_ratio_pct")),
        "realized_pnl": _quote_pnl_decimal(
            metrics,
            "realized_pnl",
            "realized_pnl_quote",
            task=task,
            instrument=instrument,
        ),
        "unrealized_pnl": _quote_pnl_decimal(
            metrics,
            "unrealized_pnl",
            "unrealized_pnl_quote",
            task=task,
            instrument=instrument,
        ),
        "add_count": _decimal(metrics.get("snowball_net_add_count")),
    }
    if extracted["margin_ratio_pct"] is None:
        margin_ratio = _decimal(metrics.get("margin_ratio"))
        if margin_ratio is not None:
            extracted["margin_ratio_pct"] = margin_ratio * Decimal("100")
    return {key: value for key, value in extracted.items() if value is not None}


def _apply_position_pnl_buckets(
    *,
    buckets: dict[int, dict[str, Decimal]],
    task: Any,
    task_type_label: str,
    execution_id: Any,
    since: datetime,
    until: datetime,
) -> None:
    if not buckets:
        return

    base_filter = {
        "task_type": task_type_label,
        "task_id": task.pk,
        "execution_id": execution_id,
    }
    if not Position.objects.filter(**base_filter).exists():
        return

    bucket_times = sorted(buckets)
    closed_positions = list(
        Position.objects.filter(
            **base_filter,
            exit_time__isnull=False,
            exit_time__lte=until,
        )
        .exclude(exit_price__isnull=True)
        .order_by("exit_time", "id")
        .values_list("exit_time", "direction", "entry_price", "exit_price", "units")
    )
    realized_pnl = Decimal("0")
    closed_index = 0
    for bucket in bucket_times:
        bucket_at = datetime.fromtimestamp(bucket, tz=UTC)
        while closed_index < len(closed_positions):
            exit_time, direction, entry_price, exit_price, units = closed_positions[closed_index]
            if exit_time is None or exit_time > bucket_at:
                break
            realized_pnl += _position_realized_pnl(
                direction=direction,
                entry_price=entry_price,
                exit_price=exit_price,
                units=units,
            )
            closed_index += 1
        buckets[bucket]["realized_pnl"] = realized_pnl

    open_window_start = datetime.fromtimestamp(bucket_times[0], tz=UTC)
    positions = list(
        Position.objects.filter(
            **base_filter,
            entry_time__lte=until,
        )
        .filter(Q(exit_time__isnull=True) | Q(exit_time__gte=open_window_start))
        .order_by("entry_time", "id")
        .values_list("entry_time", "exit_time", "direction", "entry_price", "units")
    )
    for bucket in bucket_times:
        current_price = buckets[bucket].get("current_price")
        if current_price is None:
            continue
        bucket_at = datetime.fromtimestamp(bucket, tz=UTC)
        unrealized_pnl = Decimal("0")
        for entry_time, exit_time, direction, entry_price, units in positions:
            if entry_time > bucket_at or (exit_time is not None and exit_time <= bucket_at):
                continue
            unrealized_pnl += _position_unrealized_pnl(
                direction=direction,
                entry_price=entry_price,
                current_price=current_price,
                units=units,
            )
        buckets[bucket]["unrealized_pnl"] = unrealized_pnl


def _position_realized_pnl(
    *,
    direction: str,
    entry_price: Decimal,
    exit_price: Decimal,
    units: int,
) -> Decimal:
    abs_units = Decimal(str(abs(units)))
    if str(direction).lower() == "short":
        return (entry_price - exit_price) * abs_units
    return (exit_price - entry_price) * abs_units


def _position_unrealized_pnl(
    *,
    direction: str,
    entry_price: Decimal,
    current_price: Decimal,
    units: int,
) -> Decimal:
    abs_units = Decimal(str(abs(units)))
    if str(direction).lower() == "short":
        return (entry_price - current_price) * abs_units
    return (current_price - entry_price) * abs_units


def _loss_cut_threshold_lines(
    *,
    task: Any,
    since: datetime,
    until: datetime,
) -> list[dict[str, Any]]:
    config = _snowball_net_config(task)
    if not config.loss_cut_enabled:
        return []

    key, label, color, label_key = LOSS_CUT_THRESHOLD_LINE_SPEC
    threshold = -float(config.loss_cut_threshold_pips)
    return [
        {
            "id": key,
            "label": label,
            "label_key": label_key,
            "color": color,
            "line_style": "dashed",
            "points": [
                {"time": int(since.timestamp()), "value": threshold},
                {"time": int(until.timestamp()), "value": threshold},
            ],
        }
    ]


def _margin_threshold_lines(
    *,
    task: Any,
    since: datetime,
    until: datetime,
) -> list[dict[str, Any]]:
    config = _snowball_net_config(task)
    values = {
        "margin_reduce_threshold_pct": config.margin_reduce_threshold_pct
        if config.margin_reduce_enabled
        else None,
        "margin_reduce_target_pct": config.margin_reduce_target_pct
        if config.margin_reduce_enabled
        else None,
        "emergency_threshold_pct": config.emergency_threshold_pct
        if config.emergency_enabled
        else None,
    }
    lines: list[dict[str, Any]] = []
    for key, label, color, label_key in MARGIN_THRESHOLD_LINE_SPECS:
        threshold = values.get(key)
        if threshold is None:
            continue
        lines.append(
            {
                "id": key,
                "label": label,
                "label_key": label_key,
                "color": color,
                "line_style": "dashed",
                "points": [
                    {"time": int(since.timestamp()), "value": float(threshold)},
                    {"time": int(until.timestamp()), "value": float(threshold)},
                ],
            }
        )
    return lines


def _next_add_price_lines(
    *,
    task: Any,
    buckets: dict[int, dict[str, Decimal]],
) -> list[dict[str, Any]]:
    key, label, color, label_key = NEXT_ADD_LINE_SPEC
    enabled_points: list[dict[str, Any]] = []
    disabled_points: list[dict[str, Any]] = []
    config = _snowball_net_config(task)
    pip_size = _task_pip_size(task)

    for bucket, values in sorted(buckets.items()):
        average = values.get("average_price")
        net_units = _int_decimal(values.get("net_units"), 0)
        add_count = _int_decimal(values.get("add_count"), 0)
        if average is None or net_units <= 0:
            continue

        can_add = add_count < config.max_add_count and net_units < config.effective_max_net_units
        price = values.get("next_add_price") if can_add else None
        if price is None:
            price = values.get("theoretical_next_add_price")
        if price is None:
            price = _theoretical_next_add_price(
                average=average,
                add_step=add_count + 1,
                config=config,
                pip_size=pip_size,
            )

        point = {"time": bucket, "value": float(price)}
        if can_add:
            enabled_points.append(point)
        else:
            disabled_points.append(point)

    return [
        {
            "id": key,
            "label": label,
            "label_key": label_key,
            "color": color,
            "line_style": "solid",
            "points": enabled_points,
        },
        {
            "id": f"{key}_disabled",
            "label": f"{label} disabled",
            "label_key": "snowballNet.chart.nextAddDisabled",
            "color": color,
            "line_style": "dotted",
            "points": disabled_points,
        },
    ]


def _snowball_net_config(task: Any) -> SnowballNetConfig:
    raw_config = getattr(getattr(task, "config", None), "config_dict", {})
    return SnowballNetConfig.from_dict(dict(raw_config or {}))


def _task_pip_size(task: Any) -> Decimal:
    value = getattr(task, "pip_size", None)
    if value:
        return Decimal(str(value))
    return pip_size_for_instrument(str(getattr(task, "instrument", "") or ""))


def _theoretical_next_add_price(
    *,
    average: Decimal,
    add_step: int,
    config: SnowballNetConfig,
    pip_size: Decimal,
) -> Decimal:
    offset = config.add_interval_pips(add_step) * pip_size
    if config.trade_direction == "long":
        return average - offset
    return average + offset


def _int_decimal(value: Decimal | None, default: int) -> int:
    if value is None:
        return default
    return int(value)


def _series_from_buckets(
    *,
    buckets: dict[int, dict[str, Decimal]],
    key: str,
    label: str,
    color: str,
    label_key: str,
    line_style: str | None = None,
) -> dict[str, Any]:
    series: dict[str, Any] = {
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
    if line_style is not None:
        series["line_style"] = line_style
    return series


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
    strategy_state: dict[str, Any],
    last_tick_timestamp: str | None,
    *,
    task: Any,
    instrument: str,
    pnl_currency: str | None,
    quote_currency: str | None,
) -> dict[str, Any]:
    raw_metrics = strategy_state.get("metrics")
    metrics: dict[str, Any] = (
        cast("dict[str, Any]", raw_metrics) if isinstance(raw_metrics, dict) else {}
    )
    realized_pnl = _quote_pnl_decimal(
        metrics,
        "realized_pnl",
        "realized_pnl_quote",
        task=task,
        instrument=instrument,
    )
    unrealized_pnl = _quote_pnl_decimal(
        metrics,
        "unrealized_pnl",
        "unrealized_pnl_quote",
        task=task,
        instrument=instrument,
    )
    metrics_quote_currency = _string_or_none(metrics.get("quote_currency")) or quote_currency
    return {
        "timestamp": last_tick_timestamp,
        "bid": strategy_state.get("last_bid"),
        "ask": strategy_state.get("last_ask"),
        "mid": strategy_state.get("last_mid"),
        "direction": strategy_state.get("direction"),
        "direction_mode": strategy_state.get("direction_mode"),
        "auto_direction_signal": strategy_state.get("auto_direction_signal"),
        "auto_direction_samples": strategy_state.get("auto_direction_samples"),
        "auto_direction_last_decision": strategy_state.get("auto_direction_last_decision") or {},
        "net_units": strategy_state.get("net_units"),
        "average_price": strategy_state.get("average_price"),
        "current_price": metrics.get("snowball_net_current_price"),
        "pips_from_average": metrics.get("snowball_net_pips_from_average"),
        "loss_cut_enabled": metrics.get("snowball_net_loss_cut_enabled"),
        "loss_cut_threshold_pips": metrics.get("snowball_net_loss_cut_threshold_pips"),
        "target_price": metrics.get("snowball_net_target_price"),
        "next_add_price": metrics.get("snowball_net_next_add_price"),
        "theoretical_next_add_price": metrics.get("snowball_net_theoretical_next_add_price"),
        "can_add": metrics.get("snowball_net_can_add"),
        "margin_ratio_pct": metrics.get("snowball_net_margin_ratio_pct"),
        "margin_reduce_enabled": metrics.get("snowball_net_margin_reduce_enabled"),
        "margin_reduce_threshold_pct": metrics.get("snowball_net_margin_reduce_threshold_pct"),
        "margin_reduce_target_pct": metrics.get("snowball_net_margin_reduce_target_pct"),
        "emergency_enabled": metrics.get("snowball_net_emergency_enabled"),
        "emergency_threshold_pct": metrics.get("snowball_net_emergency_threshold_pct"),
        "realized_pnl": _decimal_to_string(realized_pnl),
        "unrealized_pnl": _decimal_to_string(unrealized_pnl),
        "pnl_currency": metrics_quote_currency or pnl_currency,
        "quote_currency": metrics_quote_currency,
        "pending_action": strategy_state.get("pending_action") or {},
        "last_action": strategy_state.get("last_action") or {},
    }


def _resolve_pnl_currency(*, task: Any, instrument: str) -> str | None:
    return _quote_currency(instrument) or _account_currency(task)


def _account_currency(task: Any) -> str | None:
    account_currency = getattr(task, "account_currency", None)
    if not account_currency:
        account = getattr(task, "oanda_account", None)
        account_currency = getattr(account, "currency", None)
    return str(account_currency).strip().upper() or None


def _quote_currency(instrument: str) -> str | None:
    if "_" not in instrument:
        return None
    quote_currency = instrument.rsplit("_", 1)[-1]
    return quote_currency.strip().upper() or None


def _string_or_none(value: Any) -> str | None:
    if value in (None, ""):
        return None
    normalized = str(value).strip().upper()
    return normalized or None


def _decimal_to_string(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def _quote_pnl_decimal(
    metrics: dict[str, Any],
    account_key: str,
    quote_key: str,
    *,
    task: Any,
    instrument: str,
) -> Decimal | None:
    quote_value = _decimal(metrics.get(quote_key))
    if quote_value is not None:
        return quote_value

    account_value = _decimal(metrics.get(account_key))
    if account_value is None:
        return None

    account_currency = _account_currency(task)
    quote_currency = _quote_currency(instrument)
    if not account_currency or not quote_currency or account_currency == quote_currency:
        return account_value

    mid_price = _decimal(metrics.get("snowball_net_current_price")) or _decimal(
        metrics.get("current_price")
    )
    if mid_price is None or mid_price <= 0:
        return account_value

    conversion_rate = quote_to_account_rate(
        instrument,
        mid_price,
        account_currency=account_currency,
    )
    if conversion_rate == 0:
        return account_value
    return account_value / conversion_rate


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
