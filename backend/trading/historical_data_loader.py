"""
Historical data loader for backtesting.

This module provides functionality to load historical tick data from multiple sources:
- PostgreSQL database (TickData model)
- AWS Athena for large-scale historical data from Polygon.io
- AWS S3 for direct CSV/GZ file loading

AWS Authentication:
- Uses IAM roles for EC2/ECS instances (recommended for production)
- Supports AWS_PROFILE environment variable for profile-based authentication
- Supports AWS_ROLE_ARN environment variable for role-based authentication
- Supports AWS_CREDENTIALS_FILE for custom credentials location
- Never uses hardcoded AWS credentials

Requirements: 12.1
"""

import csv
import gzip
import io
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Literal

from django.db.models import QuerySet

from botocore.exceptions import BotoCoreError, ClientError  # pylint: disable=import-error

from trading.tick_data_models import TickData

logger = logging.getLogger(__name__)


@dataclass
class TickDataWrapper:
    """
    Lightweight wrapper that mimics TickData model interface for backtesting.

    This class provides the same attributes as the TickData Django model
    but without database dependencies, making it suitable for backtesting.
    """

    instrument: str
    timestamp: datetime
    bid: Decimal
    ask: Decimal
    mid: Decimal
    spread: Decimal

    # Optional attributes that strategies might access
    account: Any = None
    created_at: datetime | None = None

    def __post_init__(self) -> None:
        """Set created_at to timestamp if not provided."""
        if self.created_at is None:
            self.created_at = self.timestamp


@dataclass
class TickDataPoint:
    """
    Normalized tick data point for backtesting.

    Attributes:
        instrument: Currency pair (e.g., 'EUR_USD')
        timestamp: Timestamp of the tick
        bid: Bid price
        ask: Ask price
        mid: Mid price (average of bid and ask)
        spread: Spread (difference between ask and bid)
    """

    instrument: str
    timestamp: datetime
    bid: Decimal
    ask: Decimal
    mid: Decimal
    spread: Decimal

    def to_tick_data(self) -> "TickDataWrapper":
        """
        Convert TickDataPoint to TickData-compatible wrapper for strategy consumption.

        Returns:
            TickDataWrapper instance with same interface as TickData model
        """
        return TickDataWrapper(
            instrument=self.instrument,
            timestamp=self.timestamp,
            bid=self.bid,
            ask=self.ask,
            mid=self.mid,
            spread=self.spread,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TickDataPoint":
        """
        Create TickDataPoint from dictionary.

        Args:
            data: Dictionary containing tick data

        Returns:
            TickDataPoint instance
        """
        return cls(
            instrument=data["instrument"],
            timestamp=data["timestamp"],
            bid=Decimal(str(data["bid"])),
            ask=Decimal(str(data["ask"])),
            mid=Decimal(str(data.get("mid", (data["bid"] + data["ask"]) / 2))),
            spread=Decimal(str(data.get("spread", data["ask"] - data["bid"]))),
        )

    @classmethod
    def from_tick_data_model(cls, tick: TickData) -> "TickDataPoint":
        """
        Create TickDataPoint from TickData model instance.

        Args:
            tick: TickData model instance

        Returns:
            TickDataPoint instance
        """
        return cls(
            instrument=tick.instrument,
            timestamp=tick.timestamp,
            bid=tick.bid,
            ask=tick.ask,
            mid=tick.mid,
            spread=tick.spread,
        )

    def to_dict(self) -> dict[str, Any]:
        """
        Convert TickDataPoint to dictionary.

        Returns:
            Dictionary representation of tick data
        """
        return {
            "instrument": self.instrument,
            "timestamp": self.timestamp.isoformat(),
            "bid": float(self.bid),
            "ask": float(self.ask),
            "mid": float(self.mid),
            "spread": float(self.spread),
        }


class HistoricalDataLoader:
    """
    Load historical tick data from multiple sources.

    Supports loading data from:
    - PostgreSQL database (TickData model)
    - AWS Athena for large-scale historical data (Polygon.io format)
    - AWS S3 for direct CSV/GZ file loading

    AWS Authentication:
    - Uses IAM roles by default (recommended for production)
    - Supports AWS_PROFILE environment variable for profile-based auth
    - Supports AWS_ROLE_ARN environment variable for role-based auth
    - Supports AWS_CREDENTIALS_FILE for custom credentials location

    Requirements: 12.1
    """

    # Default S3 bucket for historical forex data (can be overridden via SystemSettings)
    DEFAULT_S3_BUCKET = "forex-hist-data-789121567207-us-west-2"
    DEFAULT_S3_PREFIX = "global_forex/quotes"

    def __init__(
        self,
        data_source: Literal["postgresql", "athena", "s3"] = "athena",
        athena_database: str | None = None,
        athena_table: str | None = None,
        athena_output_bucket: str | None = None,
        s3_bucket: str | None = None,
        s3_prefix: str | None = None,
    ):
        """
        Initialize HistoricalDataLoader.

        Args:
            data_source: Data source to use ('postgresql', 'athena', or 's3')
            athena_database: Athena database name (default: forex_hist_data_db)
            athena_table: Athena table name (default: quotes)
            athena_output_bucket: S3 bucket for Athena query results
            s3_bucket: S3 bucket for direct file loading
            s3_prefix: S3 key prefix for tick data files
        """
        self.data_source = data_source
        self.athena_database = athena_database or self._get_system_setting(
            "athena_database_name", "forex_hist_data_db"
        )
        self.athena_table = athena_table or self._get_system_setting("athena_table_name", "quotes")
        self.athena_output_bucket = athena_output_bucket or self._get_system_setting(
            "athena_output_bucket", ""
        )
        self.athena_query_timeout = int(self._get_system_setting("athena_query_timeout", "600"))

        # S3 configuration
        self.s3_bucket = s3_bucket or self._get_system_setting(
            "s3_data_bucket", self.DEFAULT_S3_BUCKET
        )
        self.s3_prefix = s3_prefix or self._get_system_setting(
            "s3_data_prefix", self.DEFAULT_S3_PREFIX
        )

        # Initialize AWS clients if using Athena or S3 source
        self.athena_client = None
        self.s3_client = None
        if self.data_source == "athena":
            self._initialize_aws_clients()
        elif self.data_source == "s3":
            self._initialize_s3_client()

    def _is_expired_token_error(self, error: Exception) -> bool:
        """
        Check if the error is due to expired AWS credentials.

        Args:
            error: The exception to check

        Returns:
            True if the error is an expired token error
        """
        error_str = str(error)
        return (
            "ExpiredTokenException" in error_str
            or "ExpiredToken" in error_str
            or "security token included in the request is expired" in error_str.lower()
        )

    def _refresh_aws_clients(self) -> None:
        """
        Refresh AWS clients by re-initializing with fresh credentials.

        This is called when an ExpiredTokenException is detected.
        """
        logger.info("Refreshing AWS credentials due to token expiration")
        if self.data_source == "athena":
            self._initialize_aws_clients()
        elif self.data_source == "s3":
            self._initialize_s3_client()

    def _get_system_setting(self, key: str, default: str) -> str:
        """
        Get configuration value from SystemSettings model.

        Args:
            key: Configuration key
            default: Default value if not found

        Returns:
            Configuration value or default
        """
        try:
            from accounts.models import SystemSettings

            system_settings = SystemSettings.objects.first()
            if system_settings:
                return str(getattr(system_settings, key, default))
            return default
        except Exception:  # pylint: disable=broad-exception-caught
            return default

    def _initialize_aws_clients(self) -> None:
        """
        Initialize AWS Athena client with proper authentication.

        Authentication priority:
        1. System Settings (database configuration)
        2. Environment variables (AWS_PROFILE, AWS_ROLE_ARN, AWS_CREDENTIALS_FILE)
        3. IAM role (default for EC2/ECS instances)

        Never uses hardcoded AWS_ACCESS_KEY_ID or AWS_SECRET_ACCESS_KEY.
        """
        try:
            # Import here to avoid circular dependency
            from accounts.email_utils import get_aws_session

            logger.info("Initializing AWS clients for Athena using system settings")

            # Use the centralized AWS session logic from email_utils
            # This respects system settings configuration
            session = get_aws_session()

            # Initialize Athena client
            self.athena_client = session.client("athena")
            logger.info("Athena client initialized successfully")

        except (BotoCoreError, ClientError) as e:
            logger.error("Failed to initialize AWS clients: %s", e)
            raise RuntimeError(f"AWS client initialization failed: {e}") from e

    def _initialize_s3_client(self) -> None:
        """
        Initialize AWS S3 client with proper authentication.

        Authentication priority:
        1. System Settings (database configuration)
        2. Environment variables (AWS_PROFILE, AWS_ROLE_ARN, AWS_CREDENTIALS_FILE)
        3. IAM role (default for EC2/ECS instances)

        Never uses hardcoded AWS_ACCESS_KEY_ID or AWS_SECRET_ACCESS_KEY.
        """
        try:
            # Import here to avoid circular dependency
            from accounts.email_utils import get_aws_session

            logger.info("Initializing AWS S3 client using system settings")

            # Use the centralized AWS session logic from email_utils
            # This respects system settings configuration
            session = get_aws_session()

            # Initialize S3 client
            self.s3_client = session.client("s3")
            logger.info("S3 client initialized successfully")

        except (BotoCoreError, ClientError) as e:
            logger.error("Failed to initialize S3 client: %s", e)
            raise RuntimeError(f"S3 client initialization failed: {e}") from e

    def load_data(
        self,
        instrument: str,
        start_date: datetime,
        end_date: datetime,
    ) -> list[TickDataPoint]:
        """
        Load historical tick data for the specified instrument and date range.

        Args:
            instrument: Currency pair (e.g., 'EUR_USD')
            start_date: Start date for data retrieval
            end_date: End date for data retrieval

        Returns:
            List of TickDataPoint objects sorted by timestamp

        Raises:
            ValueError: If data source is invalid or required parameters are missing
            RuntimeError: If data loading fails
        """
        if self.data_source == "postgresql":
            return self._load_from_postgresql(instrument, start_date, end_date)
        if self.data_source == "athena":
            return self._load_from_athena(instrument, start_date, end_date)
        if self.data_source == "s3":
            return self._load_from_s3(instrument, start_date, end_date)
        raise ValueError(f"Invalid data source: {self.data_source}")

    def _load_from_postgresql(
        self,
        instrument: str,
        start_date: datetime,
        end_date: datetime,
    ) -> list[TickDataPoint]:
        """
        Load tick data from PostgreSQL database.

        Args:
            instrument: Currency pair
            start_date: Start date
            end_date: End date

        Returns:
            List of TickDataPoint objects
        """
        logger.info(
            "Loading tick data from PostgreSQL: %s from %s to %s", instrument, start_date, end_date
        )

        try:
            # Query TickData model
            queryset: QuerySet[TickData] = TickData.objects.filter(
                instrument=instrument,
                timestamp__gte=start_date,
                timestamp__lte=end_date,
            ).order_by("timestamp")

            # Convert to TickDataPoint objects
            tick_data = [TickDataPoint.from_tick_data_model(tick) for tick in queryset]

            logger.info("Loaded %d ticks from PostgreSQL", len(tick_data))
            return tick_data

        except Exception as e:
            logger.error("Failed to load data from PostgreSQL: %s", e)
            raise RuntimeError(f"PostgreSQL data loading failed: {e}") from e

    def _load_from_athena(
        self,
        instrument: str,
        start_date: datetime,
        end_date: datetime,
    ) -> list[TickDataPoint]:
        """
        Load tick data from Athena (Polygon.io format).

        Polygon.io format:
        - ticker: e.g., "C:EUR-USD"
        - ask_price, bid_price: prices
        - participant_timestamp: nanoseconds since epoch
        - year, month, day: partition keys

        Args:
            instrument: Currency pair (e.g., 'EUR_USD')
            start_date: Start date
            end_date: End date

        Returns:
            List of TickDataPoint objects

        Raises:
            ValueError: If Athena database or output bucket is not configured
            RuntimeError: If Athena query fails
        """
        if not self.athena_database:
            raise ValueError("Athena database not configured")
        if not self.athena_output_bucket:
            raise ValueError("Athena output bucket not configured")
        if not self.athena_client:
            raise RuntimeError("Athena client not initialized")

        logger.info(
            "Loading tick data from Athena: %s from %s to %s", instrument, start_date, end_date
        )

        try:
            # Build Athena query
            query = self._build_athena_query(instrument, start_date, end_date)

            # Execute Athena query
            query_execution_id = self._execute_athena_query(query)

            # Wait for query completion
            self._wait_for_query_completion(
                query_execution_id, max_wait_seconds=self.athena_query_timeout
            )

            # Fetch query results
            tick_data = self._fetch_query_results(query_execution_id)

            logger.info("Loaded %d ticks from Athena", len(tick_data))
            return tick_data

        except Exception as e:
            logger.error("Failed to load data from Athena: %s", e)
            raise RuntimeError(f"Athena data loading failed: {e}") from e

    def _build_athena_query(
        self,
        instrument: str,
        start_date: datetime,
        end_date: datetime,
    ) -> str:
        """
        Build Athena SQL query for Polygon.io tick data retrieval.

        Converts instrument format: EUR_USD -> C:EUR-USD
        Converts timestamp from nanoseconds to datetime

        Args:
            instrument: Currency pair (e.g., 'EUR_USD')
            start_date: Start date
            end_date: End date

        Returns:
            SQL query string
        """
        # Convert instrument format: EUR_USD -> C:EUR-USD
        polygon_ticker = f"C:{instrument.replace('_', '-')}"

        # Convert dates to timestamps (nanoseconds)
        start_timestamp_ns = int(start_date.timestamp() * 1_000_000_000)
        end_timestamp_ns = int(end_date.timestamp() * 1_000_000_000)

        # Extract partition values for efficient querying
        # Note: Partition columns are stored as strings in Athena with zero-padding
        start_year = str(start_date.year)
        start_month = str(start_date.month).zfill(2)
        start_day = str(start_date.day).zfill(2)
        end_year = str(end_date.year)
        end_month = str(end_date.month).zfill(2)
        end_day = str(end_date.day).zfill(2)

        # Build partition filter for efficient scanning
        # If same day, use exact partition
        if start_date.date() == end_date.date():
            partition_filter = (
                f"year = '{start_year}' AND month = '{start_month}' " f"AND day = '{start_day}'"
            )
        # If same month, filter by month and day range
        elif start_year == end_year and start_month == end_month:
            partition_filter = (
                f"year = '{start_year}' AND month = '{start_month}' "
                f"AND day >= '{start_day}' AND day <= '{end_day}'"
            )
        # If same year, filter by year and month/day range
        elif start_year == end_year:
            partition_filter = (
                f"year = '{start_year}' AND "
                f"((month = '{start_month}' AND day >= '{start_day}') OR "
                f"(month > '{start_month}' AND month < '{end_month}') OR "
                f"(month = '{end_month}' AND day <= '{end_day}'))"
            )
        # Different years - use year range
        else:
            partition_filter = (
                f"((year = '{start_year}' AND month >= '{start_month}') OR "
                f"(year > '{start_year}' AND year < '{end_year}') OR "
                f"(year = '{end_year}' AND month <= '{end_month}'))"
            )

        # SQL query uses controlled inputs (config, datetime objects), not user strings
        query = f"""
        SELECT
            ticker,
            bid_price,
            ask_price,
            participant_timestamp
        FROM "{self.athena_database}"."{self.athena_table}"
        WHERE {partition_filter}
            AND ticker = '{polygon_ticker}'
            AND participant_timestamp >= {start_timestamp_ns}
            AND participant_timestamp <= {end_timestamp_ns}
        ORDER BY participant_timestamp ASC
        """  # nosec B608

        logger.info(
            "Query partition filter: %s (scanning %s to %s)",
            partition_filter,
            start_date.date(),
            end_date.date(),
        )

        return query

    def _execute_athena_query(self, query: str, retry_on_expired: bool = True) -> str:
        """
        Execute Athena query and return execution ID.

        Handles expired token errors by refreshing credentials and retrying.

        Args:
            query: SQL query string
            retry_on_expired: Whether to retry on expired token (default True)

        Returns:
            Query execution ID

        Raises:
            RuntimeError: If query execution fails
        """
        if not self.athena_client:
            raise RuntimeError("Athena client not initialized")

        try:
            # Define output location for query results
            output_location = f"s3://{self.athena_output_bucket}/athena-results/"

            logger.info(
                "Executing Athena query - Database: %s, Table: %s, Output: %s",
                self.athena_database,
                self.athena_table,
                output_location,
            )
            logger.debug("Query: %s", query)

            # Execute query
            response = self.athena_client.start_query_execution(
                QueryString=query,
                QueryExecutionContext={"Database": self.athena_database},
                ResultConfiguration={"OutputLocation": output_location},
            )

            query_execution_id = response["QueryExecutionId"]
            logger.info(
                "Athena query started: %s (view in console: "
                "https://console.aws.amazon.com/athena/home?region=%s"
                "#query/history/%s)",
                query_execution_id,
                self.athena_client.meta.region_name,
                query_execution_id,
            )
            return query_execution_id

        except (BotoCoreError, ClientError) as e:
            # Check if this is an expired token error and retry
            if retry_on_expired and self._is_expired_token_error(e):
                logger.warning(
                    "AWS credentials expired during query execution, refreshing and retrying"
                )
                self._refresh_aws_clients()
                return self._execute_athena_query(query, retry_on_expired=False)

            logger.error("Failed to execute Athena query: %s", e)
            raise RuntimeError(f"Athena query execution failed: {e}") from e

    def _wait_for_query_completion(
        self,
        query_execution_id: str,
        max_wait_seconds: int = 600,  # Increased to 10 minutes for large queries
    ) -> None:
        """
        Wait for Athena query to complete.

        Handles expired token errors by refreshing credentials and retrying.

        Args:
            query_execution_id: Query execution ID
            max_wait_seconds: Maximum time to wait in seconds

        Raises:
            RuntimeError: If query fails or times out
        """
        if not self.athena_client:
            raise RuntimeError("Athena client not initialized")

        import time

        elapsed = 0
        last_log_time = 0
        log_interval = 30  # Log every 30 seconds

        while elapsed < max_wait_seconds:
            try:
                response = self.athena_client.get_query_execution(
                    QueryExecutionId=query_execution_id
                )
                status = response["QueryExecution"]["Status"]["State"]

                # Log progress periodically
                if elapsed - last_log_time >= log_interval:
                    stats = response["QueryExecution"].get("Statistics", {})
                    data_scanned = stats.get("DataScannedInBytes", 0)
                    execution_time = stats.get("EngineExecutionTimeInMillis", 0)
                    logger.info(
                        "Athena query %s status: %s (elapsed: %ds, "
                        "data scanned: %.2f MB, execution time: %.2fs)",
                        query_execution_id,
                        status,
                        elapsed,
                        data_scanned / (1024 * 1024),
                        execution_time / 1000,
                    )
                    last_log_time = elapsed

                if status == "SUCCEEDED":
                    stats = response["QueryExecution"].get("Statistics", {})
                    data_scanned = stats.get("DataScannedInBytes", 0)
                    execution_time = stats.get("EngineExecutionTimeInMillis", 0)
                    logger.info(
                        "Athena query completed: %s "
                        "(data scanned: %.2f MB, execution time: %.2fs)",
                        query_execution_id,
                        data_scanned / (1024 * 1024),
                        execution_time / 1000,
                    )
                    return
                if status in ["FAILED", "CANCELLED"]:
                    reason = response["QueryExecution"]["Status"].get(
                        "StateChangeReason", "Unknown"
                    )
                    error_message = (
                        response["QueryExecution"]["Status"]
                        .get("AthenaError", {})
                        .get("ErrorMessage", "No error message")
                    )
                    logger.error(
                        "Athena query %s: %s - Reason: %s, Error: %s",
                        status,
                        query_execution_id,
                        reason,
                        error_message,
                    )
                    raise RuntimeError(f"Athena query {status}: {reason} - {error_message}")

                # Wait before checking again
                time.sleep(2)
                elapsed += 2

            except (BotoCoreError, ClientError) as e:
                # Check if this is an expired token error
                if self._is_expired_token_error(e):
                    logger.warning(
                        "AWS credentials expired during query wait, refreshing and continuing"
                    )
                    self._refresh_aws_clients()
                    # Continue the loop - don't increment elapsed for refresh time
                    continue

                logger.error("Failed to check query status: %s", e)
                raise RuntimeError(f"Query status check failed: {e}") from e

        # Log final status before timing out
        try:
            response = self.athena_client.get_query_execution(QueryExecutionId=query_execution_id)
            status = response["QueryExecution"]["Status"]["State"]
            stats = response["QueryExecution"].get("Statistics", {})
            logger.error(
                "Athena query timed out after %d seconds. Final status: %s, Statistics: %s",
                max_wait_seconds,
                status,
                stats,
            )
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.debug("Could not retrieve final query status: %s", e)

        raise RuntimeError(f"Athena query timed out after {max_wait_seconds} seconds")

    def _fetch_query_results(  # pylint: disable=too-many-locals
        self, query_execution_id: str, retry_on_expired: bool = True
    ) -> list[TickDataPoint]:
        """
        Fetch results from completed Athena query and convert Polygon.io format.

        Polygon.io format:
        - ticker: "C:EUR-USD" -> convert to "EUR_USD"
        - bid_price, ask_price: Decimal values
        - participant_timestamp: nanoseconds since epoch -> convert to datetime

        Args:
            query_execution_id: Query execution ID
            retry_on_expired: Whether to retry on expired token (default True)

        Returns:
            List of TickDataPoint objects

        Raises:
            RuntimeError: If fetching results fails
        """
        if not self.athena_client:
            raise RuntimeError("Athena client not initialized")

        try:
            tick_data: list[TickDataPoint] = []
            paginator = self.athena_client.get_paginator("get_query_results")

            for page in paginator.paginate(QueryExecutionId=query_execution_id):
                # Skip header row
                rows = page["ResultSet"]["Rows"][1:]

                for row in rows:
                    data = row["Data"]

                    # Extract values
                    ticker = data[0]["VarCharValue"]  # e.g., "C:EUR-USD"
                    bid_price = Decimal(data[1]["VarCharValue"])
                    ask_price = Decimal(data[2]["VarCharValue"])
                    timestamp_ns = int(data[3]["VarCharValue"])

                    # Convert ticker format: C:EUR-USD -> EUR_USD
                    instrument = ticker.replace("C:", "").replace("-", "_")

                    # Convert timestamp from nanoseconds to timezone-aware datetime (UTC)
                    timestamp = datetime.fromtimestamp(
                        timestamp_ns / 1_000_000_000, tz=timezone.utc
                    )

                    # Calculate mid and spread
                    mid = (bid_price + ask_price) / 2
                    spread = ask_price - bid_price

                    tick = TickDataPoint(
                        instrument=instrument,
                        timestamp=timestamp,
                        bid=bid_price,
                        ask=ask_price,
                        mid=mid,
                        spread=spread,
                    )
                    tick_data.append(tick)

            return tick_data

        except (BotoCoreError, ClientError) as e:
            # Check if this is an expired token error and retry
            if retry_on_expired and self._is_expired_token_error(e):
                logger.warning(
                    "AWS credentials expired during results fetch, refreshing and retrying"
                )
                self._refresh_aws_clients()
                return self._fetch_query_results(query_execution_id, retry_on_expired=False)

            logger.error("Failed to fetch query results: %s", e)
            raise RuntimeError(f"Query results fetch failed: {e}") from e

    def normalize_data(self, raw_data: list[dict[str, Any]]) -> list[TickDataPoint]:
        """
        Normalize raw tick data from various sources.

        Args:
            raw_data: List of raw tick data dictionaries

        Returns:
            List of normalized TickDataPoint objects
        """
        normalized_data: list[TickDataPoint] = []

        for data in raw_data:
            try:
                tick = TickDataPoint.from_dict(data)
                normalized_data.append(tick)
            except (KeyError, ValueError) as e:
                logger.warning("Failed to normalize tick data: %s", e)
                continue

        return normalized_data

    def _load_from_s3(
        self,
        instrument: str,
        start_date: datetime,
        end_date: datetime,
    ) -> list[TickDataPoint]:
        """
        Load tick data directly from S3 compressed CSV files.

        File path format:
        {bucket}/{prefix}/year={YYYY}/month={MM}/day={DD}/{YYYY}-{MM}-{DD}.csv.gz

        CSV format (Polygon.io):
        - ticker: e.g., "C:EUR-USD"
        - ask_price, bid_price: prices
        - participant_timestamp: nanoseconds since epoch

        Args:
            instrument: Currency pair (e.g., 'EUR_USD')
            start_date: Start date
            end_date: End date

        Returns:
            List of TickDataPoint objects

        Raises:
            ValueError: If S3 bucket is not configured
            RuntimeError: If S3 operations fail
        """
        if not self.s3_bucket:
            raise ValueError("S3 bucket not configured")
        if not self.s3_client:
            raise RuntimeError("S3 client not initialized")

        logger.info("Loading tick data from S3: %s from %s to %s", instrument, start_date, end_date)

        # Convert instrument format for filtering: EUR_USD -> C:EUR-USD
        polygon_ticker = f"C:{instrument.replace('_', '-')}"

        # Convert timestamps for filtering
        start_timestamp_ns = int(start_date.timestamp() * 1_000_000_000)
        end_timestamp_ns = int(end_date.timestamp() * 1_000_000_000)

        tick_data: list[TickDataPoint] = []

        try:
            # Iterate through each day in the date range
            current_date = start_date.date()
            end_date_only = end_date.date()

            while current_date <= end_date_only:
                # Build S3 key for this day's file
                s3_key = self._build_s3_key(current_date)

                try:
                    # Load and process the file for this day
                    day_ticks = self._load_s3_file(
                        s3_key,
                        polygon_ticker,
                        start_timestamp_ns,
                        end_timestamp_ns,
                        instrument,
                    )
                    tick_data.extend(day_ticks)
                    logger.info(
                        "Loaded %d ticks from S3 for %s on %s",
                        len(day_ticks),
                        instrument,
                        current_date.isoformat(),
                    )
                except self.s3_client.exceptions.NoSuchKey:
                    logger.warning("S3 file not found for %s: %s", current_date.isoformat(), s3_key)
                except Exception as e:  # pylint: disable=broad-exception-caught
                    logger.warning(
                        "Failed to load S3 file for %s: %s - %s",
                        current_date.isoformat(),
                        s3_key,
                        e,
                    )

                # Move to next day
                current_date += timedelta(days=1)

            logger.info("Loaded %d total ticks from S3", len(tick_data))
            return tick_data

        except Exception as e:
            logger.error("Failed to load data from S3: %s", e)
            raise RuntimeError(f"S3 data loading failed: {e}") from e

    def _build_s3_key(self, date: Any) -> str:
        """
        Build S3 key for a specific date's data file.

        Path format: {prefix}/year={YYYY}/month={MM}/day={DD}/{YYYY}-{MM}-{DD}.csv.gz

        Args:
            date: Date object for which to build the key

        Returns:
            S3 key string
        """
        year = str(date.year)
        month = str(date.month).zfill(2)
        day = str(date.day).zfill(2)
        date_str = f"{year}-{month}-{day}"

        return f"{self.s3_prefix}/year={year}/month={month}/day={day}/{date_str}.csv.gz"

    def _parse_s3_row(
        self,
        row: dict[str, str],
        polygon_ticker: str,
        start_timestamp_ns: int,
        end_timestamp_ns: int,
        instrument: str,
    ) -> TickDataPoint | None:
        """
        Parse a single CSV row from S3 file into a TickDataPoint.

        Args:
            row: CSV row as dictionary
            polygon_ticker: Ticker in Polygon.io format (e.g., "C:EUR-USD")
            start_timestamp_ns: Start timestamp in nanoseconds
            end_timestamp_ns: End timestamp in nanoseconds
            instrument: Instrument in our format (e.g., "EUR_USD")

        Returns:
            TickDataPoint if row is valid and matches filters, None otherwise
        """
        # Filter by ticker
        if row.get("ticker", "") != polygon_ticker:
            return None

        # Filter by timestamp
        try:
            timestamp_ns = int(row.get("participant_timestamp", 0))
        except (ValueError, TypeError):
            return None

        if timestamp_ns < start_timestamp_ns or timestamp_ns > end_timestamp_ns:
            return None

        # Parse prices
        try:
            bid_price = Decimal(row.get("bid_price", "0"))
            ask_price = Decimal(row.get("ask_price", "0"))
        except (ValueError, TypeError, ArithmeticError):
            logger.warning("Invalid price data in row: %s", row)
            return None

        # Skip invalid prices
        if bid_price <= 0 or ask_price <= 0:
            return None

        # Convert timestamp from nanoseconds to timezone-aware datetime (UTC)
        timestamp = datetime.fromtimestamp(timestamp_ns / 1_000_000_000, tz=timezone.utc)

        return TickDataPoint(
            instrument=instrument,
            timestamp=timestamp,
            bid=bid_price,
            ask=ask_price,
            mid=(bid_price + ask_price) / 2,
            spread=ask_price - bid_price,
        )

    def _load_s3_file(
        self,
        s3_key: str,
        polygon_ticker: str,
        start_timestamp_ns: int,
        end_timestamp_ns: int,
        instrument: str,
    ) -> list[TickDataPoint]:
        """
        Load and parse a single S3 file.

        Downloads the gzipped CSV file, decompresses it, parses the content,
        filters by ticker and timestamp range.

        Args:
            s3_key: S3 object key
            polygon_ticker: Ticker in Polygon.io format (e.g., "C:EUR-USD")
            start_timestamp_ns: Start timestamp in nanoseconds
            end_timestamp_ns: End timestamp in nanoseconds
            instrument: Instrument in our format (e.g., "EUR_USD")

        Returns:
            List of TickDataPoint objects for matching records
        """
        if not self.s3_client:
            raise RuntimeError("S3 client not initialized")

        logger.debug("Downloading S3 file: s3://%s/%s", self.s3_bucket, s3_key)

        # Download and decompress the file
        response = self.s3_client.get_object(Bucket=self.s3_bucket, Key=s3_key)
        decompressed_data = gzip.decompress(response["Body"].read())

        # Parse CSV content
        reader = csv.DictReader(io.StringIO(decompressed_data.decode("utf-8")))

        tick_data: list[TickDataPoint] = []
        for row in reader:
            tick = self._parse_s3_row(
                row, polygon_ticker, start_timestamp_ns, end_timestamp_ns, instrument
            )
            if tick:
                tick_data.append(tick)

        return tick_data
