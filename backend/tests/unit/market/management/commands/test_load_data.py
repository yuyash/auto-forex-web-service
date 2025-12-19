from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

import pytest
import boto3
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.market.models import TickData


@dataclass
class _FakePaginator:
    pages: list[dict[str, Any]]

    def paginate(self, **kwargs) -> Iterable[dict[str, Any]]:  # noqa: ARG002
        return iter(self.pages)


class _FakeAthenaClient:
    def __init__(self, *, pages: list[dict[str, Any]]):
        self._pages = pages

    def start_query_execution(self, **kwargs) -> dict[str, Any]:  # noqa: ARG002
        return {"QueryExecutionId": "q-123"}

    def get_query_execution(self, **kwargs) -> dict[str, Any]:  # noqa: ARG002
        return {
            "QueryExecution": {
                "Status": {
                    "State": "SUCCEEDED",
                    "StateChangeReason": "",
                }
            }
        }

    def get_paginator(self, name: str) -> _FakePaginator:
        assert name == "get_query_results"
        return _FakePaginator(self._pages)


class _FakeSession:
    def __init__(self, *, pages: list[dict[str, Any]]):
        self._pages = pages

    def client(self, name: str):
        assert name == "athena"
        return _FakeAthenaClient(pages=self._pages)


def _make_athena_page(
    *, ticker: str, participant_timestamp: str, bid_price: str, ask_price: str
) -> dict[str, Any]:
    return {
        "ResultSet": {
            "Rows": [
                {
                    "Data": [
                        {"VarCharValue": "ticker"},
                        {"VarCharValue": "bid_price"},
                        {"VarCharValue": "ask_price"},
                        {"VarCharValue": "participant_timestamp"},
                    ]
                },
                {
                    "Data": [
                        {"VarCharValue": ticker},
                        {"VarCharValue": bid_price},
                        {"VarCharValue": ask_price},
                        {"VarCharValue": participant_timestamp},
                    ]
                },
            ]
        }
    }


def _make_athena_page_with_duplicate_ticks(*, ticker: str) -> dict[str, Any]:
    """Return a single Athena page containing duplicate PK rows.

    Both rows share the same participant_timestamp (and thus the same
    (instrument, timestamp) after conversion), but have different prices.
    """

    return {
        "ResultSet": {
            "Rows": [
                {
                    "Data": [
                        {"VarCharValue": "ticker"},
                        {"VarCharValue": "bid_price"},
                        {"VarCharValue": "ask_price"},
                        {"VarCharValue": "participant_timestamp"},
                    ]
                },
                {
                    "Data": [
                        {"VarCharValue": ticker},
                        {"VarCharValue": "1.10000"},
                        {"VarCharValue": "1.10010"},
                        {"VarCharValue": "1704067200000000000"},
                    ]
                },
                {
                    "Data": [
                        {"VarCharValue": ticker},
                        {"VarCharValue": "1.20000"},
                        {"VarCharValue": "1.20010"},
                        {"VarCharValue": "1704067200000000000"},
                    ]
                },
            ]
        }
    }


@pytest.mark.django_db
def test_load_tick_data_athena_inserts_rows(monkeypatch) -> None:
    pages = [
        _make_athena_page(
            ticker="C:EURUSD",
            participant_timestamp="1704067200000000000",
            bid_price="1.10000",
            ask_price="1.10010",
        )
    ]

    monkeypatch.setattr(boto3, "Session", lambda *args, **kwargs: _FakeSession(pages=pages))

    call_command(
        "load_data",
        start="2024-01-01",
        end="2024-01-02",
        database="db",
        table="tbl",
        profile="test",
        instrument="C:EURUSD",
    )

    assert TickData.objects.count() == 1
    tick = TickData.objects.first()
    assert tick is not None
    assert tick.instrument == "EUR_USD"
    assert str(tick.bid) == "1.10000"
    assert str(tick.ask) == "1.10010"
    assert str(tick.mid) == "1.10005"


@pytest.mark.django_db
def test_load_tick_data_athena_rejects_invalid_range(monkeypatch) -> None:
    pages: list[dict[str, Any]] = []
    monkeypatch.setattr(boto3, "Session", lambda *args, **kwargs: _FakeSession(pages=pages))

    with pytest.raises(CommandError):
        call_command(
            "load_data",
            start="2024-01-02",
            end="2024-01-01",
            database="db",
            table="tbl",
        )


@pytest.mark.django_db
def test_load_tick_data_athena_dedupes_conflicting_rows_in_batch(monkeypatch) -> None:
    pages = [_make_athena_page_with_duplicate_ticks(ticker="C:EURUSD")]
    monkeypatch.setattr(boto3, "Session", lambda *args, **kwargs: _FakeSession(pages=pages))

    call_command(
        "load_data",
        start="2024-01-01",
        end="2024-01-02",
        database="db",
        table="tbl",
        profile="test",
        instrument="C:EURUSD",
    )

    assert TickData.objects.count() == 1
    tick = TickData.objects.first()
    assert tick is not None
    assert tick.instrument == "EUR_USD"
    # Last value wins when duplicates exist.
    assert str(tick.bid) == "1.20000"
    assert str(tick.ask) == "1.20010"
    assert str(tick.mid) == "1.20005"
