#!/usr/bin/env python
"""Test the view directly to see the actual error."""

import os
import sys

# Setup Django
backend_path = os.path.join(os.path.dirname(__file__), "backend")
sys.path.insert(0, backend_path)
os.chdir(backend_path)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from django.test import RequestFactory

from apps.accounts.models import User
from apps.trading.views import BacktestTaskViewSet


def test_view():
    """Test the trades endpoint directly."""
    try:
        # Get user
        user = User.objects.first()
        if not user:
            print("❌ No user found")
            return

        # Create request
        factory = RequestFactory()
        request = factory.get("/api/trading/tasks/backtest/6/trades/")
        request.user = user

        # Create viewset
        viewset = BacktestTaskViewSet()
        viewset.request = request
        viewset.format_kwarg = None
        viewset.kwargs = {"pk": 6}

        # Call trades action
        print("Calling trades() endpoint...")
        response = viewset.trades(request, pk=6)

        print(f"Status: {response.status_code}")
        print(f"Data: {response.data}")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_view()
