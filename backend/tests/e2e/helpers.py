"""Shared constants, markers, and utilities for E2E tests."""

from __future__ import annotations

import csv
import os
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Iterator

import pytest

from apps.trading.dataclasses import Tick
from apps.trading.tasks.source import TickDataSource

E2E_PASSWORD = "E2eTestPass!99"  # nosec B105

OANDA_ACCOUNT_ID = os.getenv("OANDA_ACCOUNT_ID", "")
OANDA_API_TOKEN = os.getenv("OANDA_API_TOKEN", "")


def has_oanda_credentials() -> bool:
    """Check if real OANDA credentials are available."""
    return bool(OANDA_ACCOUNT_ID and OANDA_API_TOKEN)


skip_without_oanda = pytest.mark.skipif(
    not has_oanda_credentials(),
    reason="OANDA_ACCOUNT_ID / OANDA_API_TOKEN not set",
)


class CsvTickDataSource(TickDataSource):
    """Tick data source that reads from a CSV file."""

    def __init__(self, csv_path: Path, batch_size: int = 100) -> None:
        self.csv_path = csv_path
        self.batch_size = batch_size

    def __iter__(self) -> Iterator[list[Tick]]:
        batch: list[Tick] = []
        with self.csv_path.open(newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ts_str = row["timestamp"]
                if ts_str.endswith("Z"):
                    ts_str = ts_str[:-1] + "+00:00"
                ts = datetime.fromisoformat(ts_str)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=UTC)
                tick = Tick(
                    instrument=row["instrument"],
                    timestamp=ts,
                    bid=Decimal(row["bid"]),
                    ask=Decimal(row["ask"]),
                    mid=Decimal(row["mid"]),
                )
                batch.append(tick)
                if len(batch) >= self.batch_size:
                    yield batch
                    batch = []
        if batch:
            yield batch

    def close(self) -> None:
        pass
