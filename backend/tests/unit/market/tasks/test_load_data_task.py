"""Tests for the periodic Athena tick data load task."""

from __future__ import annotations

from typing import Any

import pytest
from freezegun import freeze_time

from apps.market.models import MarketEvent
from apps.market.tasks.load_data import load_daily_tick_data


LOAD_DATA_ENV_KEYS = [
    "LOAD_DATA_DATABASE",
    "LOAD_DATA_TABLE",
    "LOAD_DATA_INSTRUMENT",
    "LOAD_DATA_AWS_PROFILE",
    "LOAD_DATA_ROLE_ARN",
    "LOAD_DATA_OUTPUT_BUCKET",
]


def _clear_load_data_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in LOAD_DATA_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


@pytest.mark.django_db
@freeze_time("2026-05-03 17:00:00", tz_offset=0)
def test_load_daily_tick_data_loads_only_yesterday(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The daily task should pass a single date to load_data, not a two-day range."""
    _clear_load_data_env(monkeypatch)
    monkeypatch.setenv("LOAD_DATA_DATABASE", "ticks_db")
    monkeypatch.setenv("LOAD_DATA_TABLE", "ticks_table")
    monkeypatch.setenv("LOAD_DATA_INSTRUMENT", "C:USD-JPY")

    calls: list[dict[str, Any]] = []

    def fake_call_command(*_args: Any, **kwargs: Any) -> None:
        calls.append(kwargs)
        kwargs["stdout"].write("Inserted 123 tick rows for 2026-05-02..2026-05-02\n")
        kwargs["stdout"].write("Inserted 123 tick rows\n")

    monkeypatch.setattr("django.core.management.call_command", fake_call_command)

    result = load_daily_tick_data.run()

    assert result == {
        "status": "completed",
        "date": "2026-05-02",
        "instrument": "C:USD-JPY",
        "rows_inserted": 123,
    }
    assert len(calls) == 1
    assert calls[0]["start"] == "2026-05-02"
    assert calls[0]["end"] == "2026-05-02"

    events = list(MarketEvent.objects.order_by("created_at", "id"))
    assert [event.event_type for event in events] == [
        "tick_data_load_started",
        "tick_data_load_completed",
    ]
    completed = events[-1]
    assert completed.category == "tick_data_load"
    assert completed.instrument == "C:USD-JPY"
    assert completed.details["date"] == "2026-05-02"
    assert completed.details["rows_inserted"] == 123
    assert completed.details["command_output"].endswith("Inserted 123 tick rows")


@pytest.mark.django_db
def test_load_daily_tick_data_persists_skip_event(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_load_data_env(monkeypatch)

    result = load_daily_tick_data.run()

    assert result == {"status": "skipped", "reason": "not configured"}
    event = MarketEvent.objects.get(event_type="tick_data_load_skipped")
    assert event.category == "tick_data_load"
    assert event.severity == "warning"
    assert event.details["missing_fields"] == [
        "LOAD_DATA_DATABASE",
        "LOAD_DATA_TABLE",
    ]
