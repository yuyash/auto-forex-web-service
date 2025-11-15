"""
Unit tests for HistoricalDataLoader.

Tests S3 data loading, Athena query execution, PostgreSQL tick data loading,
data source selection, and data normalization.

Requirements: 12.1
"""

from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import BotoCoreError, ClientError

from accounts.models import User
from trading.historical_data_loader import HistoricalDataLoader, TickDataPoint
from trading.models import OandaAccount
from trading.tick_data_models import TickData


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123",
    )


@pytest.fixture
def oanda_account(user):
    """Create a test OANDA account."""
    return OandaAccount.objects.create(
        user=user,
        account_id="001-001-1234567-001",
        api_token="test-token-12345",
        api_type="practice",
        balance=10000.00,
    )


@pytest.fixture
def sample_tick_data_models(db, oanda_account):
    """Create sample TickData model instances."""
    base_time = datetime(2024, 1, 1, 12, 0, 0)
    ticks = []
    for i in range(5):
        tick = TickData.objects.create(
            account=oanda_account,
            instrument="EUR_USD",
            timestamp=base_time + timedelta(seconds=i),
            bid=Decimal("1.1000") + Decimal(str(i * 0.0001)),
            ask=Decimal("1.1002") + Decimal(str(i * 0.0001)),
            mid=Decimal("1.1001") + Decimal(str(i * 0.0001)),
            spread=Decimal("0.0002"),
        )
        ticks.append(tick)
    return ticks


@pytest.fixture
def sample_raw_tick_data():
    """Create sample raw tick data dictionaries."""
    base_time = datetime(2024, 1, 1, 12, 0, 0)
    return [
        {
            "instrument": "EUR_USD",
            "timestamp": base_time + timedelta(seconds=i),
            "bid": 1.1000 + i * 0.0001,
            "ask": 1.1002 + i * 0.0001,
            "mid": 1.1001 + i * 0.0001,
            "spread": 0.0002,
        }
        for i in range(5)
    ]


@pytest.fixture
def mock_boto3_session():
    """Create mock boto3 session."""
    session = Mock()
    s3_client = Mock()
    athena_client = Mock()
    session.client.side_effect = lambda service: (s3_client if service == "s3" else athena_client)
    return session, s3_client, athena_client


class TestTickDataPoint:
    """Test TickDataPoint dataclass."""

    def test_from_dict(self):
        """Test creating TickDataPoint from dictionary."""
        data = {
            "instrument": "EUR_USD",
            "timestamp": datetime(2024, 1, 1, 12, 0, 0),
            "bid": 1.1000,
            "ask": 1.1002,
            "mid": 1.1001,
            "spread": 0.0002,
        }

        tick = TickDataPoint.from_dict(data)

        assert tick.instrument == "EUR_USD"
        assert tick.timestamp == datetime(2024, 1, 1, 12, 0, 0)
        assert tick.bid == Decimal("1.1000")
        assert tick.ask == Decimal("1.1002")
        assert tick.mid == Decimal("1.1001")
        assert tick.spread == Decimal("0.0002")

    def test_from_dict_calculates_mid_and_spread(self):
        """Test TickDataPoint calculates mid and spread if not provided."""
        data = {
            "instrument": "EUR_USD",
            "timestamp": datetime(2024, 1, 1, 12, 0, 0),
            "bid": 1.1000,
            "ask": 1.1002,
        }

        tick = TickDataPoint.from_dict(data)

        assert tick.mid == Decimal("1.1001")
        # Use quantize to compare with proper precision (4 decimal places)
        assert tick.spread.quantize(Decimal("0.0001")) == Decimal("0.0002")

    def test_from_tick_data_model(self, db, oanda_account):
        """Test creating TickDataPoint from TickData model."""
        tick_model = TickData.objects.create(
            account=oanda_account,
            instrument="EUR_USD",
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
            bid=Decimal("1.1000"),
            ask=Decimal("1.1002"),
            mid=Decimal("1.1001"),
            spread=Decimal("0.0002"),
        )

        tick = TickDataPoint.from_tick_data_model(tick_model)

        assert tick.instrument == "EUR_USD"
        assert tick.timestamp == datetime(2024, 1, 1, 12, 0, 0)
        assert tick.bid == Decimal("1.1000")
        assert tick.ask == Decimal("1.1002")
        assert tick.mid == Decimal("1.1001")
        assert tick.spread == Decimal("0.0002")

    def test_to_dict(self):
        """Test converting TickDataPoint to dictionary."""
        tick = TickDataPoint(
            instrument="EUR_USD",
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
            bid=Decimal("1.1000"),
            ask=Decimal("1.1002"),
            mid=Decimal("1.1001"),
            spread=Decimal("0.0002"),
        )

        data = tick.to_dict()

        assert data["instrument"] == "EUR_USD"
        assert data["timestamp"] == "2024-01-01T12:00:00"
        assert data["bid"] == 1.1000
        assert data["ask"] == 1.1002
        assert data["mid"] == 1.1001
        assert data["spread"] == 0.0002


class TestHistoricalDataLoaderInitialization:
    """Test HistoricalDataLoader initialization."""

    def test_initialization_postgresql_source(self):
        """Test initialization with PostgreSQL data source."""
        loader = HistoricalDataLoader(data_source="postgresql")

        assert loader.data_source == "postgresql"
        assert loader.athena_client is None

    def test_initialization_athena_source_with_config(self):
        """Test initialization with Athena data source and configuration."""
        with patch("accounts.email_utils.get_aws_session") as mock_get_session:
            mock_session = Mock()
            mock_athena_client = Mock()
            mock_session.client.return_value = mock_athena_client
            mock_get_session.return_value = mock_session

            loader = HistoricalDataLoader(
                data_source="athena",
                athena_database="test-db",
                athena_output_bucket="test-bucket",
            )

            assert loader.data_source == "athena"
            assert loader.athena_database == "test-db"
            assert loader.athena_output_bucket == "test-bucket"
            assert loader.athena_client == mock_athena_client


class TestAWSClientInitialization:
    """Test AWS client initialization with different authentication methods."""

    def test_aws_client_initialization_default(self):
        """Test AWS client initialization with default credentials."""
        with patch("accounts.email_utils.get_aws_session") as mock_get_session:
            mock_session = Mock()
            mock_athena_client = Mock()
            mock_session.client.return_value = mock_athena_client
            mock_get_session.return_value = mock_session

            loader = HistoricalDataLoader(
                data_source="athena",
                athena_database="test-db",
                athena_output_bucket="test-bucket",
            )

            # Verify session was created
            mock_get_session.assert_called_once()
            assert loader.athena_client == mock_athena_client

    def test_aws_client_initialization_with_profile(self):
        """Test AWS client initialization with AWS_PROFILE."""
        with (
            patch.dict("os.environ", {"AWS_PROFILE": "test-profile"}),
            patch("accounts.email_utils.get_aws_session") as mock_get_session,
        ):
            mock_session = Mock()
            mock_athena_client = Mock()
            mock_session.client.return_value = mock_athena_client
            mock_get_session.return_value = mock_session

            loader = HistoricalDataLoader(
                data_source="athena",
                athena_database="test-db",
                athena_output_bucket="test-bucket",
            )

            # Verify session was created
            mock_get_session.assert_called_once()
            assert loader.athena_client == mock_athena_client

    def test_aws_client_initialization_with_role_arn(self):
        """Test AWS client initialization with AWS_ROLE_ARN."""
        with (
            patch.dict("os.environ", {"AWS_ROLE_ARN": "arn:aws:iam::123456789:role/test"}),
            patch("accounts.email_utils.get_aws_session") as mock_get_session,
        ):
            mock_session = Mock()
            mock_athena_client = Mock()
            mock_session.client.return_value = mock_athena_client
            mock_get_session.return_value = mock_session

            loader = HistoricalDataLoader(
                data_source="athena",
                athena_database="test-db",
                athena_output_bucket="test-bucket",
            )

            # Verify session was created
            mock_get_session.assert_called_once()
            assert loader.athena_client == mock_athena_client

    def test_aws_client_initialization_with_credentials_file(self):
        """Test AWS client initialization with AWS_CREDENTIALS_FILE."""
        with (
            patch.dict("os.environ", {"AWS_CREDENTIALS_FILE": "/path/to/credentials"}),
            patch("accounts.email_utils.get_aws_session") as mock_get_session,
        ):
            mock_session = Mock()
            mock_athena_client = Mock()
            mock_session.client.return_value = mock_athena_client
            mock_get_session.return_value = mock_session

            loader = HistoricalDataLoader(
                data_source="athena",
                athena_database="test-db",
                athena_output_bucket="test-bucket",
            )

            # Verify session was created
            mock_get_session.assert_called_once()
            assert loader.athena_client == mock_athena_client

    def test_aws_client_initialization_failure(self):
        """Test AWS client initialization handles failures."""
        with patch("accounts.email_utils.get_aws_session") as mock_get_session:
            mock_get_session.side_effect = BotoCoreError()

            with pytest.raises(RuntimeError) as exc_info:
                HistoricalDataLoader(
                    data_source="athena",
                    athena_database="test-db",
                    athena_output_bucket="test-bucket",
                )

            assert "AWS client initialization failed" in str(exc_info.value)


class TestPostgreSQLDataLoading:
    """Test loading data from PostgreSQL."""

    def test_load_from_postgresql(self, sample_tick_data_models):
        """Test loading tick data from PostgreSQL."""
        loader = HistoricalDataLoader(data_source="postgresql")

        start_date = datetime(2024, 1, 1, 12, 0, 0)
        end_date = datetime(2024, 1, 1, 12, 0, 10)

        tick_data = loader.load_data("EUR_USD", start_date, end_date)

        assert len(tick_data) == 5
        assert all(isinstance(tick, TickDataPoint) for tick in tick_data)
        assert tick_data[0].instrument == "EUR_USD"
        assert tick_data[0].bid == Decimal("1.1000")

    def test_load_from_postgresql_empty_result(self, db):
        """Test loading from PostgreSQL with no matching data."""
        loader = HistoricalDataLoader(data_source="postgresql")

        start_date = datetime(2024, 1, 1, 12, 0, 0)
        end_date = datetime(2024, 1, 1, 12, 0, 10)

        tick_data = loader.load_data("GBP_USD", start_date, end_date)

        assert len(tick_data) == 0

    def test_load_from_postgresql_date_filtering(self, sample_tick_data_models):
        """Test PostgreSQL data loading filters by date correctly."""
        loader = HistoricalDataLoader(data_source="postgresql")

        # Query for only first 2 ticks
        start_date = datetime(2024, 1, 1, 12, 0, 0)
        end_date = datetime(2024, 1, 1, 12, 0, 1)

        tick_data = loader.load_data("EUR_USD", start_date, end_date)

        assert len(tick_data) == 2

    def test_load_from_postgresql_sorted_by_timestamp(self, sample_tick_data_models):
        """Test PostgreSQL data is sorted by timestamp."""
        loader = HistoricalDataLoader(data_source="postgresql")

        start_date = datetime(2024, 1, 1, 12, 0, 0)
        end_date = datetime(2024, 1, 1, 12, 0, 10)

        tick_data = loader.load_data("EUR_USD", start_date, end_date)

        # Verify timestamps are in ascending order
        for i in range(len(tick_data) - 1):
            assert tick_data[i].timestamp <= tick_data[i + 1].timestamp


class TestAthenaDataLoading:
    """Test loading data from Athena."""

    def test_load_from_athena_success(self):
        """Test successful data loading from Athena."""
        with patch("accounts.email_utils.get_aws_session") as mock_get_session:
            mock_session = Mock()
            mock_athena_client = Mock()
            mock_session.client.return_value = mock_athena_client
            mock_get_session.return_value = mock_session

            # Mock Athena query execution
            mock_athena_client.start_query_execution.return_value = {
                "QueryExecutionId": "test-query-id"
            }

            # Mock query completion
            mock_athena_client.get_query_execution.return_value = {
                "QueryExecution": {"Status": {"State": "SUCCEEDED"}}
            }

            # Mock query results (Polygon.io format)
            mock_athena_client.get_paginator.return_value.paginate.return_value = [
                {
                    "ResultSet": {
                        "Rows": [
                            {"Data": []},  # Header row
                            {
                                "Data": [
                                    {"VarCharValue": "C:EUR-USD"},
                                    {"VarCharValue": "1.1000"},
                                    {"VarCharValue": "1.1002"},
                                    {"VarCharValue": "1704110400000000000"},  # nanoseconds
                                ]
                            },
                        ]
                    }
                }
            ]

            loader = HistoricalDataLoader(
                data_source="athena",
                athena_database="test-db",
                athena_output_bucket="test-bucket",
            )

            start_date = datetime(2024, 1, 1, 12, 0, 0)
            end_date = datetime(2024, 1, 1, 12, 0, 10)

            tick_data = loader.load_data("EUR_USD", start_date, end_date)

            assert len(tick_data) == 1
            assert tick_data[0].instrument == "EUR_USD"
            assert tick_data[0].bid == Decimal("1.1000")

    def test_load_from_athena_missing_bucket(self):
        """Test Athena loading fails without output bucket configuration."""
        with patch("accounts.email_utils.get_aws_session"):
            loader = HistoricalDataLoader(data_source="athena", athena_database="test-db")
            loader.athena_output_bucket = ""

            start_date = datetime(2024, 1, 1, 12, 0, 0)
            end_date = datetime(2024, 1, 1, 12, 0, 10)

            with pytest.raises(ValueError) as exc_info:
                loader.load_data("EUR_USD", start_date, end_date)

            assert "Athena output bucket not configured" in str(exc_info.value)

    def test_load_from_athena_missing_database(self):
        """Test Athena loading fails without database configuration."""
        with patch("accounts.email_utils.get_aws_session"):
            loader = HistoricalDataLoader(data_source="athena", athena_output_bucket="test-bucket")
            loader.athena_database = ""

            start_date = datetime(2024, 1, 1, 12, 0, 0)
            end_date = datetime(2024, 1, 1, 12, 0, 10)

            with pytest.raises(ValueError) as exc_info:
                loader.load_data("EUR_USD", start_date, end_date)

            assert "Athena database not configured" in str(exc_info.value)

    def test_athena_query_execution_failure(self):
        """Test handling of Athena query execution failure."""
        with patch("accounts.email_utils.get_aws_session") as mock_get_session:
            mock_session = Mock()
            mock_athena_client = Mock()
            mock_session.client.return_value = mock_athena_client
            mock_get_session.return_value = mock_session

            # Mock query execution failure
            mock_athena_client.start_query_execution.side_effect = ClientError(
                {"Error": {"Code": "InvalidRequestException", "Message": "Query failed"}},
                "StartQueryExecution",
            )

            loader = HistoricalDataLoader(
                data_source="athena",
                athena_database="test-db",
                athena_output_bucket="test-bucket",
            )

            start_date = datetime(2024, 1, 1, 12, 0, 0)
            end_date = datetime(2024, 1, 1, 12, 0, 10)

            with pytest.raises(RuntimeError) as exc_info:
                loader.load_data("EUR_USD", start_date, end_date)

            assert "Athena data loading failed" in str(exc_info.value)

    def test_athena_query_timeout(self):
        """Test handling of Athena query timeout."""
        with patch("accounts.email_utils.get_aws_session") as mock_get_session:
            mock_session = Mock()
            mock_athena_client = Mock()
            mock_session.client.return_value = mock_athena_client
            mock_get_session.return_value = mock_session

            # Mock query execution
            mock_athena_client.start_query_execution.return_value = {
                "QueryExecutionId": "test-query-id"
            }

            # Mock query still running
            mock_athena_client.get_query_execution.return_value = {
                "QueryExecution": {"Status": {"State": "RUNNING"}}
            }

            loader = HistoricalDataLoader(
                data_source="athena",
                athena_database="test-db",
                athena_output_bucket="test-bucket",
            )

            # Patch time.sleep to avoid actual waiting
            with patch("time.sleep"):
                with pytest.raises(RuntimeError) as exc_info:
                    loader._wait_for_query_completion("test-query-id", max_wait_seconds=1)

                assert "timed out" in str(exc_info.value)

    def test_athena_query_failed_status(self):
        """Test handling of Athena query FAILED status."""
        with patch("accounts.email_utils.get_aws_session") as mock_get_session:
            mock_session = Mock()
            mock_athena_client = Mock()
            mock_session.client.return_value = mock_athena_client
            mock_get_session.return_value = mock_session

            # Mock query execution
            mock_athena_client.start_query_execution.return_value = {
                "QueryExecutionId": "test-query-id"
            }

            # Mock query failed
            mock_athena_client.get_query_execution.return_value = {
                "QueryExecution": {
                    "Status": {"State": "FAILED", "StateChangeReason": "Syntax error"}
                }
            }

            loader = HistoricalDataLoader(
                data_source="athena",
                athena_database="test-db",
                athena_output_bucket="test-bucket",
            )

            with pytest.raises(RuntimeError) as exc_info:
                loader._wait_for_query_completion("test-query-id")

            assert "FAILED" in str(exc_info.value)


class TestDataSourceSelection:
    """Test data source selection logic."""

    def test_load_data_postgresql_source(self, sample_tick_data_models):
        """Test load_data uses PostgreSQL when configured."""
        loader = HistoricalDataLoader(data_source="postgresql")

        start_date = datetime(2024, 1, 1, 12, 0, 0)
        end_date = datetime(2024, 1, 1, 12, 0, 10)

        tick_data = loader.load_data("EUR_USD", start_date, end_date)

        assert len(tick_data) > 0
        assert all(isinstance(tick, TickDataPoint) for tick in tick_data)

    def test_load_data_athena_source(self):
        """Test load_data uses Athena when configured."""
        with patch("accounts.email_utils.get_aws_session") as mock_get_session:
            mock_session = Mock()
            mock_athena_client = Mock()
            mock_session.client.return_value = mock_athena_client
            mock_get_session.return_value = mock_session

            # Mock Athena operations
            mock_athena_client.start_query_execution.return_value = {
                "QueryExecutionId": "test-query-id"
            }
            mock_athena_client.get_query_execution.return_value = {
                "QueryExecution": {"Status": {"State": "SUCCEEDED"}}
            }
            mock_athena_client.get_paginator.return_value.paginate.return_value = [
                {"ResultSet": {"Rows": [{"Data": []}]}}
            ]

            loader = HistoricalDataLoader(
                data_source="athena",
                athena_database="test-db",
                athena_output_bucket="test-bucket",
            )

            start_date = datetime(2024, 1, 1, 12, 0, 0)
            end_date = datetime(2024, 1, 1, 12, 0, 10)

            tick_data = loader.load_data("EUR_USD", start_date, end_date)

            # Verify Athena was called
            mock_athena_client.start_query_execution.assert_called_once()
            assert isinstance(tick_data, list)

    def test_load_data_invalid_source(self):
        """Test load_data raises error for invalid data source."""
        loader = HistoricalDataLoader(data_source="postgresql")
        loader.data_source = "invalid"  # type: ignore[assignment]

        start_date = datetime(2024, 1, 1, 12, 0, 0)
        end_date = datetime(2024, 1, 1, 12, 0, 10)

        with pytest.raises(ValueError) as exc_info:
            loader.load_data("EUR_USD", start_date, end_date)

        assert "Invalid data source" in str(exc_info.value)


class TestDataNormalization:
    """Test data normalization functionality."""

    def test_normalize_data_success(self, sample_raw_tick_data):
        """Test normalizing raw tick data."""
        loader = HistoricalDataLoader(data_source="postgresql")

        normalized = loader.normalize_data(sample_raw_tick_data)

        assert len(normalized) == 5
        assert all(isinstance(tick, TickDataPoint) for tick in normalized)
        assert normalized[0].instrument == "EUR_USD"
        assert normalized[0].bid == Decimal("1.1000")

    def test_normalize_data_with_missing_fields(self):
        """Test normalizing data with missing fields."""
        loader = HistoricalDataLoader(data_source="postgresql")

        raw_data = [
            {
                "instrument": "EUR_USD",
                "timestamp": datetime(2024, 1, 1, 12, 0, 0),
                "bid": 1.1000,
                "ask": 1.1002,
                # mid and spread will be calculated
            }
        ]

        normalized = loader.normalize_data(raw_data)

        assert len(normalized) == 1
        assert normalized[0].mid == Decimal("1.1001")
        # Use quantize to compare with proper precision (4 decimal places)
        assert normalized[0].spread.quantize(Decimal("0.0001")) == Decimal("0.0002")

    def test_normalize_data_skips_invalid_entries(self):
        """Test normalizing data skips invalid entries."""
        loader = HistoricalDataLoader(data_source="postgresql")

        raw_data: list = [
            {
                "instrument": "EUR_USD",
                "timestamp": datetime(2024, 1, 1, 12, 0, 0),
                "bid": 1.1000,
                "ask": 1.1002,
            },
            {
                "instrument": "GBP_USD",
                # Missing required fields
            },
            {
                "instrument": "USD_JPY",
                "timestamp": datetime(2024, 1, 1, 12, 0, 1),
                "bid": 110.00,
                "ask": 110.02,
            },
        ]

        normalized = loader.normalize_data(raw_data)

        # Should skip the invalid entry
        assert len(normalized) == 2
        assert normalized[0].instrument == "EUR_USD"
        assert normalized[1].instrument == "USD_JPY"

    def test_normalize_data_empty_list(self):
        """Test normalizing empty data list."""
        loader = HistoricalDataLoader(data_source="postgresql")

        normalized = loader.normalize_data([])

        assert len(normalized) == 0


class TestAthenaQueryBuilding:
    """Test Athena SQL query building."""

    def test_build_athena_query(self):
        """Test building Athena SQL query for Polygon.io format."""
        with patch("accounts.email_utils.get_aws_session"):
            loader = HistoricalDataLoader(
                data_source="athena",
                athena_database="test-db",
                athena_output_bucket="test-bucket",
            )

            start_date = datetime(2024, 1, 1, 12, 0, 0)
            end_date = datetime(2024, 1, 1, 13, 0, 0)

            query = loader._build_athena_query("EUR_USD", start_date, end_date)

            assert "SELECT" in query
            assert 'FROM "test-db"' in query
            assert "C:EUR-USD" in query  # Polygon.io format
            assert "participant_timestamp" in query
            assert "ORDER BY participant_timestamp ASC" in query
