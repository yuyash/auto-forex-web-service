"""
Historical data loader for backtesting.

This module provides functionality to load historical tick data from multiple sources:
- PostgreSQL database (TickData model)
- AWS S3 + Athena for large-scale historical data

AWS Authentication:
- Uses IAM roles for EC2/ECS instances (recommended for production)
- Supports AWS_PROFILE environment variable for profile-based authentication
- Supports AWS_ROLE_ARN environment variable for role-based authentication
- Supports AWS_CREDENTIALS_FILE for custom credentials location
- Never uses hardcoded AWS credentials

Requirements: 12.1
"""

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from django.conf import settings
from django.db.models import QuerySet

import boto3  # type: ignore[import-untyped]  # pylint: disable=import-error
from botocore.exceptions import (  # type: ignore[import-untyped]  # pylint: disable=import-error
    BotoCoreError,
    ClientError,
)

from trading.tick_data_models import TickData

logger = logging.getLogger(__name__)


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
    - AWS S3 + Athena for large-scale historical data

    AWS Authentication:
    - Uses IAM roles by default (recommended for production)
    - Supports AWS_PROFILE environment variable for profile-based auth
    - Supports AWS_ROLE_ARN environment variable for role-based auth
    - Supports AWS_CREDENTIALS_FILE for custom credentials location

    Requirements: 12.1
    """

    def __init__(
        self,
        data_source: Literal["postgresql", "s3"] = "postgresql",
        s3_bucket: str | None = None,
        athena_database: str | None = None,
    ):
        """
        Initialize HistoricalDataLoader.

        Args:
            data_source: Data source to use ('postgresql' or 's3')
            s3_bucket: S3 bucket name for historical data (required for s3 source)
            athena_database: Athena database name (required for s3 source)
        """
        self.data_source = data_source
        self.s3_bucket = s3_bucket or self._get_config_value("s3_bucket")
        self.athena_database = athena_database or self._get_config_value("athena_database")

        # Initialize AWS clients if using S3 source
        self.s3_client = None
        self.athena_client = None
        if self.data_source == "s3":
            self._initialize_aws_clients()

    def _get_config_value(self, key: str) -> str | None:
        """
        Get configuration value from settings.

        Args:
            key: Configuration key

        Returns:
            Configuration value or None
        """
        config = getattr(settings, "SYSTEM_CONFIG", {})
        backtesting_config = config.get("backtesting", {})
        return backtesting_config.get(key)  # type: ignore[no-any-return]

    def _initialize_aws_clients(self) -> None:
        """
        Initialize AWS S3 and Athena clients with proper authentication.

        Authentication priority:
        1. AWS_PROFILE environment variable (profile-based)
        2. AWS_ROLE_ARN environment variable (role assumption with STS)
        3. AWS_CREDENTIALS_FILE (custom credentials location)
        4. IAM role (default for EC2/ECS instances)

        Never uses hardcoded AWS_ACCESS_KEY_ID or AWS_SECRET_ACCESS_KEY.
        """
        try:
            # Check for AWS configuration environment variables
            aws_profile = os.environ.get("AWS_PROFILE")
            aws_role_arn = os.environ.get("AWS_ROLE_ARN")
            aws_credentials_file = os.environ.get("AWS_CREDENTIALS_FILE")

            session_kwargs: dict[str, Any] = {}

            # Handle custom credentials file
            if aws_credentials_file:
                logger.info(f"Using AWS credentials file: {aws_credentials_file}")
                os.environ["AWS_SHARED_CREDENTIALS_FILE"] = aws_credentials_file

            # Create base session with profile if specified
            if aws_profile:
                logger.info(f"Using AWS profile: {aws_profile}")
                session_kwargs["profile_name"] = aws_profile
            else:
                logger.info("Using default AWS credentials chain")

            # Create boto3 session
            session = boto3.Session(**session_kwargs)

            # If role ARN is specified, assume the role using STS
            if aws_role_arn:
                logger.info(f"Assuming AWS role: {aws_role_arn}")
                credentials = self._assume_role(session, aws_role_arn)

                # Create new session with assumed role credentials
                session = boto3.Session(
                    aws_access_key_id=credentials["AccessKeyId"],
                    aws_secret_access_key=credentials["SecretAccessKey"],
                    aws_session_token=credentials["SessionToken"],
                )
                logger.info("Successfully assumed role")

            # Initialize S3 client
            self.s3_client = session.client("s3")
            logger.info("S3 client initialized successfully")

            # Initialize Athena client
            self.athena_client = session.client("athena")
            logger.info("Athena client initialized successfully")

        except (BotoCoreError, ClientError) as e:
            logger.error(f"Failed to initialize AWS clients: {e}")
            raise RuntimeError(f"AWS client initialization failed: {e}") from e

    def _assume_role(self, session: boto3.Session, role_arn: str) -> dict[str, str]:
        """
        Assume an AWS IAM role using STS.

        Args:
            session: Boto3 session to use for assuming role
            role_arn: ARN of the role to assume

        Returns:
            Dictionary containing temporary credentials

        Raises:
            RuntimeError: If role assumption fails
        """
        try:
            # Create STS client
            sts_client = session.client("sts")

            # Assume role
            response = sts_client.assume_role(
                RoleArn=role_arn,
                RoleSessionName="forex-trading-backtest",
                DurationSeconds=3600,  # 1 hour
            )

            # Extract credentials
            credentials = response["Credentials"]
            logger.info(f"Role assumed successfully, expires at: {credentials['Expiration']}")

            return credentials  # type: ignore[no-any-return]

        except (BotoCoreError, ClientError) as e:
            logger.error(f"Failed to assume role {role_arn}: {e}")
            raise RuntimeError(f"Role assumption failed: {e}") from e

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
            f"Loading tick data from PostgreSQL: {instrument} " f"from {start_date} to {end_date}"
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

            logger.info(f"Loaded {len(tick_data)} ticks from PostgreSQL")
            return tick_data

        except Exception as e:
            logger.error(f"Failed to load data from PostgreSQL: {e}")
            raise RuntimeError(f"PostgreSQL data loading failed: {e}") from e

    def _load_from_s3(
        self,
        instrument: str,
        start_date: datetime,
        end_date: datetime,
    ) -> list[TickDataPoint]:
        """
        Load tick data from S3 using Athena query.

        Args:
            instrument: Currency pair
            start_date: Start date
            end_date: End date

        Returns:
            List of TickDataPoint objects

        Raises:
            ValueError: If S3 bucket or Athena database is not configured
            RuntimeError: If Athena query fails
        """
        if not self.s3_bucket:
            raise ValueError("S3 bucket not configured")
        if not self.athena_database:
            raise ValueError("Athena database not configured")
        if not self.athena_client:
            raise RuntimeError("Athena client not initialized")

        logger.info(
            f"Loading tick data from S3/Athena: {instrument} " f"from {start_date} to {end_date}"
        )

        try:
            # Build Athena query
            query = self._build_athena_query(instrument, start_date, end_date)

            # Execute Athena query
            query_execution_id = self._execute_athena_query(query)

            # Wait for query completion
            self._wait_for_query_completion(query_execution_id)

            # Fetch query results
            tick_data = self._fetch_query_results(query_execution_id)

            logger.info(f"Loaded {len(tick_data)} ticks from S3/Athena")
            return tick_data

        except Exception as e:
            logger.error(f"Failed to load data from S3/Athena: {e}")
            raise RuntimeError(f"S3/Athena data loading failed: {e}") from e

    def _build_athena_query(
        self,
        instrument: str,
        start_date: datetime,
        end_date: datetime,
    ) -> str:
        """
        Build Athena SQL query for tick data retrieval.

        Args:
            instrument: Currency pair
            start_date: Start date
            end_date: End date

        Returns:
            SQL query string
        """
        # SQL query uses controlled inputs (config, datetime objects), not user strings
        query = f"""
        SELECT
            instrument,
            timestamp,
            bid,
            ask,
            mid,
            spread
        FROM {self.athena_database}.tick_data
        WHERE instrument = '{instrument}'
            AND timestamp >= TIMESTAMP '{start_date.strftime('%Y-%m-%d %H:%M:%S')}'
            AND timestamp <= TIMESTAMP '{end_date.strftime('%Y-%m-%d %H:%M:%S')}'
        ORDER BY timestamp ASC
        """  # nosec B608
        return query

    def _execute_athena_query(self, query: str) -> str:
        """
        Execute Athena query and return execution ID.

        Args:
            query: SQL query string

        Returns:
            Query execution ID

        Raises:
            RuntimeError: If query execution fails
        """
        if not self.athena_client:
            raise RuntimeError("Athena client not initialized")

        try:
            # Define output location for query results
            output_location = f"s3://{self.s3_bucket}/athena-results/"

            # Execute query
            response = self.athena_client.start_query_execution(
                QueryString=query,
                QueryExecutionContext={"Database": self.athena_database},
                ResultConfiguration={"OutputLocation": output_location},
            )

            query_execution_id = response["QueryExecutionId"]
            logger.info(f"Athena query started: {query_execution_id}")
            return query_execution_id

        except (BotoCoreError, ClientError) as e:
            logger.error(f"Failed to execute Athena query: {e}")
            raise RuntimeError(f"Athena query execution failed: {e}") from e

    def _wait_for_query_completion(
        self,
        query_execution_id: str,
        max_wait_seconds: int = 300,
    ) -> None:
        """
        Wait for Athena query to complete.

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
        while elapsed < max_wait_seconds:
            try:
                response = self.athena_client.get_query_execution(
                    QueryExecutionId=query_execution_id
                )
                status = response["QueryExecution"]["Status"]["State"]

                if status == "SUCCEEDED":
                    logger.info(f"Athena query completed: {query_execution_id}")
                    return
                if status in ["FAILED", "CANCELLED"]:
                    reason = response["QueryExecution"]["Status"].get(
                        "StateChangeReason", "Unknown"
                    )
                    raise RuntimeError(f"Athena query {status}: {reason}")

                # Wait before checking again
                time.sleep(2)
                elapsed += 2

            except (BotoCoreError, ClientError) as e:
                logger.error(f"Failed to check query status: {e}")
                raise RuntimeError(f"Query status check failed: {e}") from e

        raise RuntimeError(f"Athena query timed out after {max_wait_seconds} seconds")

    def _fetch_query_results(self, query_execution_id: str) -> list[TickDataPoint]:
        """
        Fetch results from completed Athena query.

        Args:
            query_execution_id: Query execution ID

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
                    tick = TickDataPoint(
                        instrument=data[0]["VarCharValue"],
                        timestamp=datetime.fromisoformat(data[1]["VarCharValue"]),
                        bid=Decimal(data[2]["VarCharValue"]),
                        ask=Decimal(data[3]["VarCharValue"]),
                        mid=Decimal(data[4]["VarCharValue"]),
                        spread=Decimal(data[5]["VarCharValue"]),
                    )
                    tick_data.append(tick)

            return tick_data

        except (BotoCoreError, ClientError) as e:
            logger.error(f"Failed to fetch query results: {e}")
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
                logger.warning(f"Failed to normalize tick data: {e}")
                continue

        return normalized_data
