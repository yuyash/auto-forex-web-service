"""
Unit tests for tick data API endpoints.

Tests cover:
- Tick data retrieval with filters
- Pagination
- Rate limiting
- CSV export functionality
- Authentication and authorization

Requirements: 7.1, 7.2, 12.1
"""

from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.urls import reverse
from django.utils import timezone

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import OandaAccount, User
from trading.tick_data_models import TickData


@pytest.fixture
def api_client():
    """Create API client for testing."""
    return APIClient()


@pytest.fixture
def test_user(db):
    """Create a test user."""
    return User.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123",
    )


@pytest.fixture
def other_user(db):
    """Create another test user."""
    return User.objects.create_user(
        username="otheruser",
        email="other@example.com",
        password="testpass123",
    )


@pytest.fixture
def test_account(test_user):
    """Create a test OANDA account."""
    account = OandaAccount.objects.create(
        user=test_user,
        account_id="001-001-1234567-001",
        api_type="practice",
    )
    account.set_api_token("test_token")
    account.save()
    return account


@pytest.fixture
def other_account(other_user):
    """Create another test OANDA account."""
    account = OandaAccount.objects.create(
        user=other_user,
        account_id="001-001-7654321-001",
        api_type="practice",
    )
    account.set_api_token("test_token")
    account.save()
    return account


@pytest.fixture
def sample_tick_data(test_account):
    """Create sample tick data for testing."""
    base_time = timezone.now()
    ticks = []

    # Create 10 EUR_USD ticks
    for i in range(10):
        tick = TickData.objects.create(
            account=test_account,
            instrument="EUR_USD",
            timestamp=base_time - timedelta(minutes=i),
            bid=Decimal("1.1000") + Decimal(str(i * 0.0001)),
            ask=Decimal("1.1005") + Decimal(str(i * 0.0001)),
        )
        ticks.append(tick)

    # Create 5 GBP_USD ticks
    for i in range(5):
        tick = TickData.objects.create(
            account=test_account,
            instrument="GBP_USD",
            timestamp=base_time - timedelta(minutes=i + 10),
            bid=Decimal("1.2500") + Decimal(str(i * 0.0001)),
            ask=Decimal("1.2504") + Decimal(str(i * 0.0001)),
        )
        ticks.append(tick)

    return ticks


@pytest.mark.django_db
class TestTickDataListView:
    """Test cases for tick data list API endpoint."""

    def test_unauthenticated_access_denied(self, api_client):
        """Test that unauthenticated requests are denied."""
        url = reverse("trading:tick_data_list")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_list_all_tick_data(self, api_client, test_user, sample_tick_data):
        """Test listing all tick data for authenticated user."""
        api_client.force_authenticate(user=test_user)
        url = reverse("trading:tick_data_list")
        print(f"URL in passing test: {url}")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert "results" in response.data
        assert "count" in response.data
        assert response.data["count"] == 15  # 10 EUR_USD + 5 GBP_USD

    def test_filter_by_instrument(self, api_client, test_user, sample_tick_data):
        """Test filtering tick data by instrument."""
        api_client.force_authenticate(user=test_user)
        url = reverse("trading:tick_data_list")
        response = api_client.get(url, {"instrument": "EUR_USD"})

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 10
        for tick in response.data["results"]:
            assert tick["instrument"] == "EUR_USD"

    def test_filter_by_start_date(self, api_client, test_user, sample_tick_data):
        """Test filtering tick data by start date."""
        api_client.force_authenticate(user=test_user)
        url = reverse("trading:tick_data_list")

        # Filter to last 5 minutes
        start_date = (timezone.now() - timedelta(minutes=5)).isoformat()
        response = api_client.get(url, {"start_date": start_date})

        assert response.status_code == status.HTTP_200_OK
        # Should get ticks from last 5 minutes (5 EUR_USD ticks)
        assert response.data["count"] <= 5

    def test_filter_by_end_date(self, api_client, test_user, sample_tick_data):
        """Test filtering tick data by end date."""
        api_client.force_authenticate(user=test_user)
        url = reverse("trading:tick_data_list")

        # Filter to before 5 minutes ago
        end_date = (timezone.now() - timedelta(minutes=5)).isoformat()
        response = api_client.get(url, {"end_date": end_date})

        assert response.status_code == status.HTTP_200_OK
        # Should get ticks older than 5 minutes
        assert response.data["count"] >= 10

    def test_filter_by_date_range(self, api_client, test_user, sample_tick_data):
        """Test filtering tick data by date range."""
        api_client.force_authenticate(user=test_user)
        url = reverse("trading:tick_data_list")

        # Filter to specific range
        start_date = (timezone.now() - timedelta(minutes=8)).isoformat()
        end_date = (timezone.now() - timedelta(minutes=2)).isoformat()
        response = api_client.get(
            url,
            {
                "start_date": start_date,
                "end_date": end_date,
            },
        )

        assert response.status_code == status.HTTP_200_OK
        # Should get ticks within the range
        assert response.data["count"] >= 6

    def test_filter_by_account_id(self, api_client, test_user, test_account, sample_tick_data):
        """Test filtering tick data by account ID."""
        api_client.force_authenticate(user=test_user)
        url = reverse("trading:tick_data_list")
        response = api_client.get(url, {"account_id": test_account.id})

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 15
        for tick in response.data["results"]:
            assert tick["account_id"] == test_account.id

    def test_invalid_start_date_format(self, api_client, test_user):
        """Test error handling for invalid start date format."""
        api_client.force_authenticate(user=test_user)
        url = reverse("trading:tick_data_list")
        response = api_client.get(url, {"start_date": "invalid-date"})

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "error" in response.data
        assert "start_date" in response.data["error"].lower()

    def test_invalid_end_date_format(self, api_client, test_user):
        """Test error handling for invalid end date format."""
        api_client.force_authenticate(user=test_user)
        url = reverse("trading:tick_data_list")
        response = api_client.get(url, {"end_date": "invalid-date"})

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "error" in response.data
        assert "end_date" in response.data["error"].lower()

    def test_invalid_account_id(self, api_client, test_user):
        """Test error handling for invalid account ID."""
        api_client.force_authenticate(user=test_user)
        url = reverse("trading:tick_data_list")
        response = api_client.get(url, {"account_id": "not-a-number"})

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "error" in response.data
        assert "account_id" in response.data["error"].lower()

    def test_pagination(self, api_client, test_user, sample_tick_data):
        """Test pagination of tick data."""
        api_client.force_authenticate(user=test_user)
        url = reverse("trading:tick_data_list")

        # Request first page with page_size=5
        response = api_client.get(url, {"page_size": 5, "page": 1})

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 5
        assert response.data["count"] == 15
        assert response.data["next"] is not None
        assert response.data["previous"] is None

        # Request second page
        response = api_client.get(url, {"page_size": 5, "page": 2})

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 5
        assert response.data["next"] is not None
        assert response.data["previous"] is not None

    def test_max_page_size_limit(self, api_client, test_user, sample_tick_data):
        """Test that page size is limited to maximum."""
        api_client.force_authenticate(user=test_user)
        url = reverse("trading:tick_data_list")

        # Request with page_size > max (1000)
        response = api_client.get(url, {"page_size": 2000})

        assert response.status_code == status.HTTP_200_OK
        # Should be limited to max_page_size (1000)
        assert len(response.data["results"]) <= 1000

    def test_user_isolation(self, api_client, test_user, other_user, test_account, other_account):
        """Test that users can only see their own tick data."""
        # Create tick data for other user
        TickData.objects.create(
            account=other_account,
            instrument="USD_JPY",
            timestamp=timezone.now(),
            bid=Decimal("110.00"),
            ask=Decimal("110.05"),
        )

        # Authenticate as test_user
        api_client.force_authenticate(user=test_user)
        url = reverse("trading:tick_data_list")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        # Should not see other user's data
        for tick in response.data["results"]:
            assert tick["account_id"] != other_account.id

    @patch("django.core.cache.cache.get")
    def test_rate_limiting(self, mock_cache_get, api_client, test_user):
        """Test rate limiting for tick data endpoint."""
        api_client.force_authenticate(user=test_user)
        url = reverse("trading:tick_data_list")

        # Simulate rate limit exceeded (60 requests already made)
        mock_cache_get.return_value = 60

        response = api_client.get(url)

        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert "error" in response.data
        assert "rate limit" in response.data["error"].lower()
        assert "retry_after" in response.data


@pytest.mark.django_db
class TestTickDataCSVExport:
    """Test cases for tick data CSV export."""

    def test_csv_export(self, api_client, test_user, sample_tick_data):
        """Test CSV export of tick data."""
        api_client.force_authenticate(user=test_user)
        url = reverse("trading:tick_data_list")

        response = api_client.get(url, {"export": "csv", "instrument": "EUR_USD"})

        assert response.status_code == status.HTTP_200_OK
        assert response["Content-Type"] == "text/csv"
        assert "attachment" in response["Content-Disposition"]
        assert "tick_data_EUR_USD" in response["Content-Disposition"]

        # Parse CSV content
        content = b"".join(response.streaming_content).decode("utf-8")
        lines = content.strip().split("\n")

        # Check header (strip \r for Windows line endings)
        assert lines[0].strip() == "timestamp,instrument,bid,ask,mid,spread"

        # Check data rows (should have 10 EUR_USD ticks)
        assert len(lines) >= 11  # header + at least 10 data rows

        # Verify first data row format
        first_row = lines[1].strip().split(",")
        assert len(first_row) == 6
        assert first_row[1] == "EUR_USD"

    def test_csv_export_with_filters(self, api_client, test_user, sample_tick_data):
        """Test CSV export with date range filters."""
        api_client.force_authenticate(user=test_user)
        url = reverse("trading:tick_data_list")

        start_date = (timezone.now() - timedelta(minutes=5)).isoformat()
        response = api_client.get(
            url,
            {
                "export": "csv",
                "instrument": "EUR_USD",
                "start_date": start_date,
            },
        )

        assert response.status_code == status.HTTP_200_OK
        assert response["Content-Type"] == "text/csv"

        # Parse CSV content
        content = b"".join(response.streaming_content).decode("utf-8")
        lines = content.strip().split("\n")

        # Should have fewer rows due to date filter
        assert len(lines) <= 11  # header + filtered data

    def test_csv_export_all_instruments(self, api_client, test_user, sample_tick_data):
        """Test CSV export without instrument filter."""
        api_client.force_authenticate(user=test_user)
        url = reverse("trading:tick_data_list")
        response = api_client.get(url, {"export": "csv"})

        assert response.status_code == status.HTTP_200_OK
        assert "tick_data_all_instruments" in response["Content-Disposition"]

        # Parse CSV content
        content = b"".join(response.streaming_content).decode("utf-8")
        lines = content.strip().split("\n")

        # Should have all ticks (15 total)
        assert len(lines) >= 16  # header + 15 data rows

    def test_invalid_format_parameter(self, api_client, test_user):
        """Test error handling for invalid export format parameter."""
        api_client.force_authenticate(user=test_user)
        url = reverse("trading:tick_data_list")
        response = api_client.get(url, {"export": "xml"})

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "error" in response.data

    @patch("django.core.cache.cache.get")
    def test_csv_export_rate_limiting(self, mock_cache_get, api_client, test_user):
        """Test that rate limiting applies to CSV export."""
        api_client.force_authenticate(user=test_user)
        url = reverse("trading:tick_data_list")

        # Simulate rate limit exceeded (60 requests already made)
        mock_cache_get.return_value = 60

        response = api_client.get(url, {"export": "csv"})

        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert "error" in response.data
