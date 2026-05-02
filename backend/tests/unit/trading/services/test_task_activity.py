"""Unit tests for task activity query services."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from apps.trading.enums import Direction, EventType, LogLevel, TaskType
from apps.trading.models import TradingEvent
from apps.trading.models.logs import TaskLog
from apps.trading.models.orders import Order, OrderStatus, OrderType
from apps.trading.models.positions import Position
from apps.trading.models.trades import Trade
from apps.trading.services.task_activity import TaskActivityQueryService
from tests.integration.factories import BacktestTaskFactory


def _request(path: str) -> Request:
    return Request(APIRequestFactory().get(path))


@pytest.mark.django_db
def test_trades_normalizes_direction_and_close_pnl():
    task = BacktestTaskFactory()
    position = Position.objects.create(
        task_type=TaskType.BACKTEST,
        task_id=task.pk,
        execution_id=task.execution_id,
        instrument="USD_JPY",
        direction=Direction.LONG,
        units=1000,
        entry_price=Decimal("150.000"),
        entry_time=datetime(2026, 1, 1, tzinfo=UTC),
        is_open=False,
    )
    Trade.objects.create(
        task_type=TaskType.BACKTEST,
        task_id=task.pk,
        execution_id=task.execution_id,
        timestamp=datetime(2026, 1, 1, 0, 1, tzinfo=UTC),
        direction=Direction.LONG,
        units=1000,
        instrument="USD_JPY",
        price=Decimal("150.100"),
        execution_method="close_position",
        position=position,
    )

    rows, total, page, page_size = TaskActivityQueryService().trades(
        request=_request("/tasks/1/trades/"),
        task=task,
        task_type_label=TaskType.BACKTEST,
    )

    assert total == 1
    assert page == 1
    assert page_size > 0
    assert rows[0]["direction"] == "buy"
    assert rows[0]["pnl"] == Decimal("100.000")


@pytest.mark.django_db
def test_positions_queryset_applies_status_and_direction_filters():
    task = BacktestTaskFactory()
    Position.objects.create(
        task_type=TaskType.BACKTEST,
        task_id=task.pk,
        execution_id=task.execution_id,
        instrument="USD_JPY",
        direction=Direction.LONG,
        units=1000,
        entry_price=Decimal("150.000"),
        entry_time=datetime(2026, 1, 1, tzinfo=UTC),
        is_open=True,
    )
    Position.objects.create(
        task_type=TaskType.BACKTEST,
        task_id=task.pk,
        execution_id=task.execution_id,
        instrument="USD_JPY",
        direction=Direction.SHORT,
        units=-1000,
        entry_price=Decimal("151.000"),
        entry_time=datetime(2026, 1, 1, tzinfo=UTC),
        is_open=False,
    )

    queryset, query = TaskActivityQueryService().positions_queryset(
        request=_request("/tasks/1/positions/?position_status=open&direction=long"),
        task=task,
        task_type_label=TaskType.BACKTEST,
    )

    assert query.position_status == "open"
    assert list(queryset.values_list("direction", flat=True)) == [Direction.LONG]


@pytest.mark.django_db
def test_log_querysets_filter_components_levels_and_position_prefix():
    task = BacktestTaskFactory()
    position = Position.objects.create(
        task_type=TaskType.BACKTEST,
        task_id=task.pk,
        execution_id=task.execution_id,
        instrument="USD_JPY",
        direction=Direction.LONG,
        units=1000,
        entry_price=Decimal("150.000"),
        entry_time=datetime(2026, 1, 1, tzinfo=UTC),
        is_open=True,
    )
    TaskLog.objects.create(
        task_type=TaskType.BACKTEST,
        task_id=task.pk,
        execution_id=task.execution_id,
        level=LogLevel.INFO,
        component="strategy",
        message="matched",
        details={"context": {"position_id": str(position.pk)}},
    )
    TaskLog.objects.create(
        task_type=TaskType.BACKTEST,
        task_id=task.pk,
        execution_id=task.execution_id,
        level=LogLevel.ERROR,
        component="transport",
        message="filtered",
        details={},
    )

    service = TaskActivityQueryService()
    queryset = service.logs_queryset(
        request=_request(
            f"/tasks/1/logs/?levels=INFO&components=strategy&position_id={str(position.pk)[:8]}"
        ),
        task=task,
        task_type_label=TaskType.BACKTEST,
    )
    components = service.log_components(
        request=_request("/tasks/1/log-components/"),
        task=task,
        task_type_label=TaskType.BACKTEST,
    )

    assert list(queryset.values_list("message", flat=True)) == ["matched"]
    assert components == ["strategy", "transport"]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("query", "expected"),
    [
        (
            "/tasks/1/logs/?message=task&message_match=partial",
            ["Backtest task execution started", "Backtest task completed"],
        ),
        (
            "/tasks/1/logs/?message=position%20opened&message_match=exact",
            ["position opened"],
        ),
        (
            "/tasks/1/logs/?message=^Backtest.*started$&message_match=regex",
            ["Backtest task execution started"],
        ),
    ],
)
def test_logs_queryset_filters_message_by_match_mode(query: str, expected: list[str]):
    task = BacktestTaskFactory()
    for message in (
        "Backtest task execution started",
        "position opened",
        "Backtest task completed",
    ):
        TaskLog.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=task.pk,
            execution_id=task.execution_id,
            level=LogLevel.INFO,
            component="strategy",
            message=message,
        )

    queryset = TaskActivityQueryService().logs_queryset(
        request=_request(query),
        task=task,
        task_type_label=TaskType.BACKTEST,
    )

    assert sorted(queryset.values_list("message", flat=True)) == sorted(expected)


@pytest.mark.django_db
def test_events_queryset_applies_scope_filters():
    task = BacktestTaskFactory()
    TradingEvent.objects.create(
        task_type=TaskType.BACKTEST,
        task_id=task.pk,
        execution_id=task.execution_id,
        event_type=EventType.STATUS_CHANGED,
        severity="info",
        description="task event",
        details={"kind": "task_started"},
    )
    TradingEvent.objects.create(
        task_type=TaskType.BACKTEST,
        task_id=task.pk,
        execution_id=task.execution_id,
        event_type=EventType.TRADE_EXECUTED,
        severity="info",
        description="trading event",
        details={},
    )

    task_events = TaskActivityQueryService().events_queryset(
        request=_request("/tasks/1/events/?scope=task"),
        task=task,
        task_type_label=TaskType.BACKTEST,
    )
    trading_events = TaskActivityQueryService().events_queryset(
        request=_request("/tasks/1/events/?scope=trading"),
        task=task,
        task_type_label=TaskType.BACKTEST,
    )

    assert list(task_events.values_list("description", flat=True)) == ["task event"]
    assert list(trading_events.values_list("description", flat=True)) == ["trading event"]


@pytest.mark.django_db
def test_orders_queryset_applies_status_type_and_direction_filters():
    task = BacktestTaskFactory()
    Order.objects.create(
        task_type=TaskType.BACKTEST,
        task_id=task.pk,
        execution_id=task.execution_id,
        instrument="USD_JPY",
        order_type=OrderType.MARKET,
        direction=Direction.LONG,
        units=1000,
        status=OrderStatus.FILLED,
    )
    Order.objects.create(
        task_type=TaskType.BACKTEST,
        task_id=task.pk,
        execution_id=task.execution_id,
        instrument="USD_JPY",
        order_type=OrderType.LIMIT,
        direction=Direction.SHORT,
        units=-1000,
        status=OrderStatus.PENDING,
    )

    queryset = TaskActivityQueryService().orders_queryset(
        request=_request("/tasks/1/orders/?status=filled&order_type=market&direction=long"),
        task=task,
        task_type_label=TaskType.BACKTEST,
    )

    assert list(queryset.values_list("direction", flat=True)) == [Direction.LONG]


@pytest.mark.django_db
def test_positions_queryset_keeps_trade_prefetch_query_count_bounded(django_assert_num_queries):
    task = BacktestTaskFactory()
    position = Position.objects.create(
        task_type=TaskType.BACKTEST,
        task_id=task.pk,
        execution_id=task.execution_id,
        instrument="USD_JPY",
        direction=Direction.LONG,
        units=1000,
        entry_price=Decimal("150.000"),
        entry_time=datetime(2026, 1, 1, tzinfo=UTC),
        is_open=True,
    )
    Trade.objects.create(
        task_type=TaskType.BACKTEST,
        task_id=task.pk,
        execution_id=task.execution_id,
        timestamp=datetime(2026, 1, 1, 0, 1, tzinfo=UTC),
        direction=Direction.LONG,
        units=1000,
        instrument="USD_JPY",
        price=Decimal("150.100"),
        execution_method="open_position",
        position=position,
    )

    queryset, _query = TaskActivityQueryService().positions_queryset(
        request=_request("/tasks/1/positions/?include_trade_ids=true"),
        task=task,
        task_type_label=TaskType.BACKTEST,
    )

    with django_assert_num_queries(2):
        rows = list(queryset[:10])
        assert [list(row.trades.all())[0].position_id for row in rows] == [position.pk]


@pytest.mark.django_db
def test_trades_query_count_stays_bounded(django_assert_num_queries):
    task = BacktestTaskFactory()
    position = Position.objects.create(
        task_type=TaskType.BACKTEST,
        task_id=task.pk,
        execution_id=task.execution_id,
        instrument="USD_JPY",
        direction=Direction.LONG,
        units=1000,
        entry_price=Decimal("150.000"),
        entry_time=datetime(2026, 1, 1, tzinfo=UTC),
        is_open=False,
    )
    Trade.objects.create(
        task_type=TaskType.BACKTEST,
        task_id=task.pk,
        execution_id=task.execution_id,
        timestamp=datetime(2026, 1, 1, 0, 1, tzinfo=UTC),
        direction=Direction.LONG,
        units=1000,
        instrument="USD_JPY",
        price=Decimal("150.100"),
        execution_method="close_position",
        position=position,
    )

    with django_assert_num_queries(2):
        rows, total, _page, _page_size = TaskActivityQueryService().trades(
            request=_request("/tasks/1/trades/"),
            task=task,
            task_type_label=TaskType.BACKTEST,
        )

    assert total == 1
    assert rows[0]["pnl"] == Decimal("100.000")


@pytest.mark.django_db
def test_trades_ordering_is_applied_before_pagination():
    task = BacktestTaskFactory()
    base_time = datetime(2026, 1, 1, tzinfo=UTC)
    prices = [Decimal("150.000"), Decimal("151.000"), Decimal("149.000")]
    for index, price in enumerate(prices):
        Trade.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=task.pk,
            execution_id=task.execution_id,
            timestamp=base_time,
            sequence_number=index,
            direction=Direction.LONG,
            units=1000,
            instrument="USD_JPY",
            price=price,
            execution_method="open_position",
        )

    rows, total, page, page_size = TaskActivityQueryService().trades(
        request=_request("/tasks/1/trades/?ordering=-price&page=2&page_size=1"),
        task=task,
        task_type_label=TaskType.BACKTEST,
    )

    assert total == 3
    assert page == 2
    assert page_size == 1
    assert rows[0]["price"] == Decimal("150.000")


@pytest.mark.django_db
def test_positions_ordering_supports_computed_realized_pnl():
    task = BacktestTaskFactory()
    base_time = datetime(2026, 1, 1, tzinfo=UTC)
    low = Position.objects.create(
        task_type=TaskType.BACKTEST,
        task_id=task.pk,
        execution_id=task.execution_id,
        instrument="USD_JPY",
        direction=Direction.LONG,
        units=1000,
        entry_price=Decimal("150.000"),
        entry_time=base_time,
        exit_price=Decimal("150.010"),
        exit_time=base_time,
        is_open=False,
    )
    high = Position.objects.create(
        task_type=TaskType.BACKTEST,
        task_id=task.pk,
        execution_id=task.execution_id,
        instrument="USD_JPY",
        direction=Direction.LONG,
        units=1000,
        entry_price=Decimal("150.000"),
        entry_time=base_time,
        exit_price=Decimal("150.100"),
        exit_time=base_time,
        is_open=False,
    )

    queryset, _query = TaskActivityQueryService().positions_queryset(
        request=_request("/tasks/1/positions/?ordering=-realized_pnl"),
        task=task,
        task_type_label=TaskType.BACKTEST,
    )

    assert list(queryset.values_list("id", flat=True)) == [high.id, low.id]


@pytest.mark.django_db
def test_orders_ordering_is_applied_to_queryset():
    task = BacktestTaskFactory()
    Order.objects.create(
        task_type=TaskType.BACKTEST,
        task_id=task.pk,
        execution_id=task.execution_id,
        instrument="USD_JPY",
        order_type=OrderType.MARKET,
        direction=Direction.LONG,
        units=1000,
        status=OrderStatus.FILLED,
    )
    larger = Order.objects.create(
        task_type=TaskType.BACKTEST,
        task_id=task.pk,
        execution_id=task.execution_id,
        instrument="USD_JPY",
        order_type=OrderType.MARKET,
        direction=Direction.LONG,
        units=3000,
        status=OrderStatus.FILLED,
    )

    queryset = TaskActivityQueryService().orders_queryset(
        request=_request("/tasks/1/orders/?ordering=-units"),
        task=task,
        task_type_label=TaskType.BACKTEST,
    )

    assert queryset.first().id == larger.id


@pytest.mark.django_db
def test_logs_ordering_is_applied_to_queryset():
    task = BacktestTaskFactory()
    for component in ("zeta", "alpha"):
        TaskLog.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=task.pk,
            execution_id=task.execution_id,
            level=LogLevel.INFO,
            component=component,
            message=component,
        )

    queryset = TaskActivityQueryService().logs_queryset(
        request=_request("/tasks/1/logs/?ordering=component"),
        task=task,
        task_type_label=TaskType.BACKTEST,
    )

    assert list(queryset.values_list("component", flat=True)) == ["alpha", "zeta"]
