"""Tests for the periodic Athena tick data load task."""

from __future__ import annotations

import logging
from typing import Any

from freezegun import freeze_time
import pytest

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


@freeze_time("2026-05-03 17:00:00", tz_offset=0)
def test_load_daily_tick_data_loads_only_yesterday(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The daily task should pass a single date to load_data, not a two-day range."""
    _clear_load_data_env(monkeypatch)
    monkeypatch.setenv("LOAD_DATA_DATABASE", "ticks_db")
    monkeypatch.setenv("LOAD_DATA_TABLE", "ticks_table")
    monkeypatch.setenv("LOAD_DATA_INSTRUMENT", "C:USD-JPY")
    caplog.set_level(logging.INFO, logger="apps.market.tasks.load_data")

    calls: list[dict[str, Any]] = []

    def fake_call_command(*_args: Any, **kwargs: Any) -> None:
        calls.append(kwargs)
        kwargs["stdout"].write("Starting Athena query for ticks_db.ticks_table\n")
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
    assert "load_data: Starting Athena query for ticks_db.ticks_table" in caplog.messages
    assert "load_data: Inserted 123 tick rows for 2026-05-02..2026-05-02" in caplog.messages
    assert "load_data: Inserted 123 tick rows" in caplog.messages


def test_load_daily_tick_data_logs_skip(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _clear_load_data_env(monkeypatch)
    caplog.set_level(logging.WARNING, logger="apps.market.tasks.load_data")

    result = load_daily_tick_data.run()

    assert result == {"status": "skipped", "reason": "not configured"}
    assert (
        "load_daily_tick_data skipped: missing Athena configuration "
        "fields=LOAD_DATA_DATABASE,LOAD_DATA_TABLE"
    ) in caplog.messages
