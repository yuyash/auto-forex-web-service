#!/usr/bin/env python
"""Test API endpoints to see actual error messages."""

import os
import sys

# Setup Django
backend_path = os.path.join(os.path.dirname(__file__), "backend")
sys.path.insert(0, backend_path)
os.chdir(backend_path)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from apps.trading.models import BacktestTasks, ExecutionEquity, ExecutionTrade


def test_endpoints():
    """Test what happens when we query the models."""
    try:
        task = BacktestTasks.objects.get(pk=6)
        print(f"✅ Task 6 found: {task.name}")
        print(f"   Status: {task.status}")
        print()

        # Test trades query
        print("Testing ExecutionTrade query...")
        try:
            trades = ExecutionTrade.objects.filter(task=task)
            print(f"✅ Trades query successful: {trades.count()} trades")
            for trade in trades[:3]:
                print(f"   - {trade}")
        except Exception as e:
            print(f"❌ Trades query failed: {e}")
            import traceback

            traceback.print_exc()
        print()

        # Test equity query
        print("Testing ExecutionEquity query...")
        try:
            equity_points = ExecutionEquity.objects.filter(task=task)
            print(f"✅ Equity query successful: {equity_points.count()} points")
            for point in equity_points[:3]:
                print(f"   - {point}")
        except Exception as e:
            print(f"❌ Equity query failed: {e}")
            import traceback

            traceback.print_exc()
        print()

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_endpoints()
