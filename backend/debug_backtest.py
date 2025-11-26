#!/usr/bin/env python
"""
Standalone backtest debugging script - No Django required!

This script allows you to debug the backtest engine directly without Django.
Perfect for:
- Quick testing and debugging
- Understanding the backtest flow
- Testing strategy logic
- Profiling performance

Usage:
    # Run with defaults (JPY_USD, 2025-11-10 to 2025-11-14, Athena)
    python debug_backtest.py

    # Custom instrument and dates (date only, time defaults to 00:00:00Z)
    python debug_backtest.py --instrument EUR_USD --start-date 2025-11-01 \
        --end-date 2025-11-05

    # With specific times in ISO 8601 format (UTC)
    python debug_backtest.py --instrument EUR_USD \
        --start-date 2025-11-01T08:00:00Z --end-date 2025-11-05T16:00:00Z

    # Use mock data (fast, no database)
    python debug_backtest.py --data-source mock --num-ticks 10000

    # Use PostgreSQL with time range (ISO 8601 format)
    python debug_backtest.py --data-source postgres --instrument EUR_USD \
        --start-date 2025-11-10T09:00:00Z --end-date 2025-11-10T17:00:00Z

    # Disable profiling
    BACKTEST_PROFILING=false python debug_backtest.py

Note: All dates and times are in UTC. Use ISO 8601 format (YYYY-MM-DDTHH:MM:SSZ)
for precise timing.

Set breakpoints in this file or in backtest_engine.py and run with debugger.
"""
# pylint: disable=too-many-lines,too-many-locals,too-many-branches,too-many-statements

import argparse
import os
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

import django

from trading.backtest_engine import BacktestConfig, BacktestEngine, BacktestTrade, EquityPoint
from trading.historical_data_loader import HistoricalDataLoader, TickDataPoint

# Add backend to path so we can import modules
backend_path = Path(__file__).parent
sys.path.insert(0, str(backend_path))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "trading_system.settings")

# Enable profiling by default for debug script
# Set to "false" to disable: BACKTEST_PROFILING=false python debug_backtest.py
if "BACKTEST_PROFILING" not in os.environ:
    os.environ["BACKTEST_PROFILING"] = "true"
    print("📊 Profiling enabled (set BACKTEST_PROFILING=false to disable)")

# Initialize Django
django.setup()


def create_mock_tick_data(instrument: str, num_ticks: int = 1000) -> list[TickDataPoint]:
    """
    Create mock tick data for testing without database or Athena.

    Generates realistic price movements for testing.

    Args:
        instrument: Currency pair (e.g., 'EUR_USD')
        num_ticks: Number of ticks to generate

    Returns:
        List of TickDataPoint objects
    """
    import random
    from datetime import timedelta

    print(f"Generating {num_ticks} mock ticks for {instrument}...")

    # Starting values
    base_price = Decimal("1.0850")
    spread = Decimal("0.0002")
    start_time = datetime(2025, 11, 10, 0, 0, 0)

    ticks = []
    current_price = base_price

    for i in range(num_ticks):
        # Random walk with slight upward bias
        change = Decimal(str(random.uniform(-0.0001, 0.00012)))  # nosec B311
        current_price += change

        # Ensure price stays in reasonable range
        current_price = max(Decimal("1.0800"), min(Decimal("1.0900"), current_price))

        # Calculate bid/ask from mid price
        mid = current_price
        bid = mid - (spread / 2)
        ask = mid + (spread / 2)

        # Create tick
        tick = TickDataPoint(
            instrument=instrument,
            timestamp=start_time + timedelta(seconds=i * 5),  # 5 seconds between ticks
            bid=bid,
            ask=ask,
            mid=mid,
            spread=spread,
        )
        ticks.append(tick)

    print(f"✓ Generated {len(ticks)} ticks")
    price_min = min(t.mid for t in ticks)
    price_max = max(t.mid for t in ticks)
    print(f"  Price range: {price_min:.5f} - {price_max:.5f}")
    return ticks


def load_real_data_from_postgres(
    instrument: str,
    start_date: datetime,
    end_date: datetime,
) -> list[TickDataPoint]:
    """
    Load real tick data from PostgreSQL database.

    Args:
        instrument: Currency pair
        start_date: Start date
        end_date: End date

    Returns:
        List of TickDataPoint objects
    """
    print("Loading real data from PostgreSQL...")
    print(f"  Instrument: {instrument}")
    print(f"  Date range: {start_date} to {end_date}")

    loader = HistoricalDataLoader(data_source="postgresql")
    tick_data = loader.load_data(
        instrument=instrument,
        start_date=start_date,
        end_date=end_date,
    )

    print(f"✓ Loaded {len(tick_data)} ticks from database")
    return tick_data


def assume_aws_role(
    role_arn: str,
    session_name: str = "backtest-debug-session",
    profile_name: str | None = None,
) -> dict[str, Any]:
    """
    Assume an AWS IAM role and return temporary credentials.

    Args:
        role_arn: ARN of the role to assume (e.g., arn:aws:iam::123456789012:role/MyRole)
        session_name: Name for the session (default: backtest-debug-session)
        profile_name: AWS profile to use for assuming the role (optional)

    Returns:
        Dictionary with temporary credentials

    Example:
        credentials = assume_aws_role("arn:aws:iam::123456789012:role/BacktestRole")
        os.environ["AWS_ACCESS_KEY_ID"] = credentials["AccessKeyId"]
        os.environ["AWS_SECRET_ACCESS_KEY"] = credentials["SecretAccessKey"]
        os.environ["AWS_SESSION_TOKEN"] = credentials["SessionToken"]
    """
    import boto3  # pylint: disable=import-error

    print(f"Assuming AWS role: {role_arn}")
    print(f"  Session name: {session_name}")
    if profile_name:
        print(f"  Using profile: {profile_name}")

    try:
        # Create boto3 session with profile if provided
        if profile_name:
            session = boto3.Session(profile_name=profile_name)
            sts_client = session.client("sts")
        else:
            sts_client = boto3.client("sts")

        # Verify current identity before assuming role
        try:
            caller_identity = sts_client.get_caller_identity()
            print(f"  Current identity: {caller_identity['Arn']}")
        except Exception as e:
            print(f"  Warning: Could not get caller identity: {e}")

        # Assume the role
        response = sts_client.assume_role(
            RoleArn=role_arn,
            RoleSessionName=session_name,
            DurationSeconds=3600,  # 1 hour
        )

        credentials: dict[str, Any] = response["Credentials"]

        print("✓ Successfully assumed role")
        print(f"  Access Key: {credentials['AccessKeyId'][:10]}...")
        print(f"  Expires: {credentials['Expiration']}")

        return credentials

    except Exception as e:
        print(f"✗ Failed to assume role: {e}")
        print("\nTroubleshooting:")
        print(f"  1. Check that profile '{profile_name}' exists in ~/.aws/credentials")
        print("  2. Verify the profile has valid credentials")
        print("  3. Ensure the profile has sts:AssumeRole permission")
        print("  4. Check the role trust policy allows your account/user")
        raise


def set_aws_credentials_from_role(role_arn: str, profile_name: str | None = None) -> None:
    """
    Assume AWS role and set environment variables with temporary credentials.

    Args:
        role_arn: ARN of the role to assume
        profile_name: AWS profile to use for assuming the role (optional)
    """
    credentials = assume_aws_role(role_arn, profile_name=profile_name)

    # Set environment variables
    os.environ["AWS_ACCESS_KEY_ID"] = credentials["AccessKeyId"]
    os.environ["AWS_SECRET_ACCESS_KEY"] = credentials["SecretAccessKey"]
    os.environ["AWS_SESSION_TOKEN"] = credentials["SessionToken"]

    print("✓ AWS credentials set in environment")


def load_data_from_athena_direct(
    instrument: str,
    start_date: datetime,
    end_date: datetime,
    athena_database: str = "forex_hist_data_db",
    athena_table: str = "quotes",
    athena_bucket: str | None = None,
    aws_profile: str | None = None,
    aws_role_arn: str | None = None,
    aws_region: str = "us-east-1",
) -> list[TickDataPoint]:
    """
    Load data directly from Athena using boto3 - NO DJANGO DEPENDENCIES.

    This is a simplified version that bypasses HistoricalDataLoader and Django.
    Perfect for debugging the backtest engine without framework overhead.
    """
    import time
    from datetime import timezone as dt_timezone

    import boto3  # pylint: disable=import-error

    print("Loading data directly from Athena (no Django)...")
    print(f"  Instrument: {instrument}")
    print(f"  Date range: {start_date} to {end_date}")
    print(f"  Database: {athena_database}")
    print(f"  Table: {athena_table}")
    print(f"  Bucket: {athena_bucket}")
    print(f"  Region: {aws_region}")

    # Create boto3 session
    if aws_role_arn:
        print(f"  Assuming role: {aws_role_arn}")
        if aws_profile:
            session = boto3.Session(profile_name=aws_profile, region_name=aws_region)
        else:
            session = boto3.Session(region_name=aws_region)

        sts = session.client("sts")
        response = sts.assume_role(
            RoleArn=aws_role_arn,
            RoleSessionName="backtest-debug",
            DurationSeconds=3600,
        )

        credentials = response["Credentials"]
        print(f"  ✓ Role assumed: {credentials['AccessKeyId'][:10]}...")

        # Create new session with temporary credentials
        session = boto3.Session(
            aws_access_key_id=credentials["AccessKeyId"],
            aws_secret_access_key=credentials["SecretAccessKey"],
            aws_session_token=credentials["SessionToken"],
            region_name=aws_region,
        )
    elif aws_profile:
        print(f"  Using profile: {aws_profile}")
        session = boto3.Session(profile_name=aws_profile, region_name=aws_region)
    else:
        print("  Using default credentials")
        session = boto3.Session(region_name=aws_region)

    athena = session.client("athena")

    # Build query
    polygon_ticker = f"C:{instrument.replace('_', '-')}"

    # Partition filter
    if start_date.date() == end_date.date():
        partition_filter = (
            f"year = '{start_date.year}' AND month = '{start_date.month:02d}' "
            f"AND day = '{start_date.day:02d}'"
        )
    else:
        partition_filter = (
            f"year = '{start_date.year}' AND month = '{start_date.month:02d}' "
            f"AND day >= '{start_date.day:02d}' AND day <= '{end_date.day:02d}'"
        )

    query = f"""
    SELECT ticker, bid_price, ask_price, participant_timestamp
    FROM "{athena_database}"."{athena_table}"
    WHERE {partition_filter}
        AND ticker = '{polygon_ticker}'
    ORDER BY participant_timestamp ASC
    """  # nosec B608

    print(f"  Executing query: {query}")

    # Execute query
    response = athena.start_query_execution(
        QueryString=query,
        QueryExecutionContext={"Database": athena_database},
        ResultConfiguration={"OutputLocation": f"s3://{athena_bucket}/athena-results/"},
    )

    query_id = response["QueryExecutionId"]
    print(f"  Query ID: {query_id}")
    print("  Waiting for query to complete...")

    # Wait for completion with progress updates
    wait_time = 0
    while True:
        status = athena.get_query_execution(QueryExecutionId=query_id)
        state = status["QueryExecution"]["Status"]["State"]

        if state == "SUCCEEDED":
            break
        if state in ["FAILED", "CANCELLED"]:
            reason = status["QueryExecution"]["Status"].get("StateChangeReason", "Unknown")
            raise RuntimeError(f"Query {state}: {reason}")

        # Log progress every 10 seconds
        if wait_time % 10 == 0 and wait_time > 0:
            elapsed_msg = f"  Still waiting... ({wait_time}s elapsed, state: {state})"
            print(elapsed_msg)

        time.sleep(2)
        wait_time += 2

    print(f"  ✓ Query completed in {wait_time}s")

    # Fetch results
    print("  Fetching results...")
    tick_data = []
    paginator = athena.get_paginator("get_query_results")
    rows_processed = 0

    for page_count, page in enumerate(paginator.paginate(QueryExecutionId=query_id), 1):
        rows = page["ResultSet"]["Rows"][1:]  # Skip header
        rows_processed += len(rows)

        # Log progress every 10 pages
        if page_count % 10 == 0:
            print(f"  Processing page {page_count}, {rows_processed} rows so far...")

        for row in rows:
            data = row["Data"]
            bid = Decimal(data[1]["VarCharValue"])
            ask = Decimal(data[2]["VarCharValue"])
            ts_ns = int(data[3]["VarCharValue"])

            # Convert to TickDataPoint
            timestamp = datetime.fromtimestamp(ts_ns / 1_000_000_000, tz=dt_timezone.utc)
            mid = (bid + ask) / 2
            spread = ask - bid

            # Filter by time range (Athena partition filter only filters by date)
            if timestamp < start_date or timestamp > end_date:
                continue

            tick = TickDataPoint(
                instrument=instrument,
                timestamp=timestamp,
                bid=bid,
                ask=ask,
                mid=mid,
                spread=spread,
            )
            tick_data.append(tick)

    rows_msg = f"✓ Loaded {len(tick_data)} ticks from {rows_processed} rows"
    print(f"{rows_msg} (filtered by time range)")
    if tick_data:
        print(f"  First tick: {tick_data[0].timestamp}")
        print(f"  Last tick:  {tick_data[-1].timestamp}")
    return tick_data


def load_real_data_from_athena(
    instrument: str,
    start_date: datetime,
    end_date: datetime,
    athena_database: str = "forex_hist_data_db",
    athena_table: str = "quotes",
    athena_bucket: str | None = None,
    aws_profile: str | None = None,
    aws_role_arn: str | None = None,
    aws_region: str | None = None,
) -> list[TickDataPoint]:
    """
    Load real tick data from AWS Athena - WRAPPER FUNCTION.

    This uses the direct boto3 approach to avoid Django dependencies.
    Perfect for debugging the backtest engine!
    """
    return load_data_from_athena_direct(
        instrument=instrument,
        start_date=start_date,
        end_date=end_date,
        athena_database=athena_database,
        athena_table=athena_table,
        athena_bucket=athena_bucket,
        aws_profile=aws_profile,
        aws_role_arn=aws_role_arn,
        aws_region=aws_region or "us-east-1",
    )


def run_backtest_with_mock_data() -> tuple[list[BacktestTrade], list[EquityPoint], dict[str, Any]]:
    """Run backtest with generated mock data - fastest for debugging."""
    print("=" * 70)
    print("BACKTEST DEBUG - Mock Data")
    print("=" * 70)

    # Configuration
    instrument = "EUR_USD"
    strategy_type = "floor"
    strategy_config = {
        "instrument": instrument,
        "position_size": 1000,
        # Add strategy-specific parameters here
    }

    # Generate mock data
    tick_data = create_mock_tick_data(instrument, num_ticks=1000)

    # Create backtest config
    config = BacktestConfig(
        strategy_type=strategy_type,
        strategy_config=strategy_config,
        instrument=instrument,
        start_date=tick_data[0].timestamp,
        end_date=tick_data[-1].timestamp,
        initial_balance=Decimal("10000"),
        commission_per_trade=Decimal("0"),
        cpu_limit=1,
        memory_limit=2 * 1024 * 1024 * 1024,  # 2GB
    )

    print("\nBacktest Configuration:")
    print(f"  Strategy: {strategy_type}")
    print(f"  Instrument: {instrument}")
    print(f"  Initial Balance: ${config.initial_balance}")
    print(f"  Ticks: {len(tick_data)}")

    # Run backtest - SET BREAKPOINT HERE
    print("\nRunning backtest...")
    engine = BacktestEngine(config)

    # Add progress callback
    def progress_callback(progress: int) -> None:
        if progress % 10 == 0:  # Log every 10%
            print(f"  Progress: {progress}%")

    engine.progress_callback = progress_callback

    # Execute - SET BREAKPOINT HERE TO DEBUG ENGINE
    trade_log, equity_curve, metrics = engine.run(tick_data)

    # Display results
    print("\n" + "=" * 70)
    print("BACKTEST RESULTS")
    print("=" * 70)
    print("\nPerformance Metrics:")
    print(f"  Total Trades:     {metrics['total_trades']}")
    print(f"  Winning Trades:   {metrics['winning_trades']}")
    print(f"  Losing Trades:    {metrics['losing_trades']}")
    print(f"  Win Rate:         {metrics['win_rate']:.2f}%")
    print(f"  Total P&L:        ${metrics['total_pnl']:.2f}")
    print(f"  Total Return:     {metrics['total_return']:.2f}%")
    print(f"  Final Balance:    ${metrics['final_balance']:.2f}")
    print(f"  Max Drawdown:     {metrics['max_drawdown']:.2f}%")

    if metrics.get("sharpe_ratio"):
        print(f"  Sharpe Ratio:     {metrics['sharpe_ratio']:.2f}")
    if metrics.get("profit_factor"):
        print(f"  Profit Factor:    {metrics['profit_factor']:.2f}")

    # Show recent trades
    if trade_log:
        print("\nRecent Trades (last 5):")
        for trade in trade_log[-5:]:
            pnl_sign = "+" if trade.pnl > 0 else ""
            trade_info = (
                f"  {trade.direction.upper():5} {trade.instrument} | "
                f"Entry: {trade.entry_price:.5f} | "
                f"Exit: {trade.exit_price:.5f} | "
                f"P&L: {pnl_sign}${trade.pnl:.2f}"
            )
            print(trade_info)

    print("\n" + "=" * 70)
    return trade_log, equity_curve, metrics


def run_backtest_with_postgres_data() -> (
    tuple[list[BacktestTrade] | None, list[EquityPoint] | None, dict[str, Any] | None]
):
    """Run backtest with real PostgreSQL data."""
    print("=" * 70)
    print("BACKTEST DEBUG - PostgreSQL Data")
    print("=" * 70)

    # Configuration
    instrument = "EUR_USD"
    start_date = datetime(2025, 11, 10)
    end_date = datetime(2025, 11, 11)
    strategy_type = "floor"
    strategy_config = {
        "instrument": instrument,
        "position_size": 1000,
    }

    # Load real data
    tick_data = load_real_data_from_postgres(instrument, start_date, end_date)

    if not tick_data:
        print("ERROR: No data found in PostgreSQL!")
        print("Try using mock data instead: run_backtest_with_mock_data()")
        return None, None, None

    # Create backtest config
    config = BacktestConfig(
        strategy_type=strategy_type,
        strategy_config=strategy_config,
        instrument=instrument,
        start_date=start_date,
        end_date=end_date,
        initial_balance=Decimal("10000"),
        commission_per_trade=Decimal("0"),
        cpu_limit=1,
        memory_limit=2 * 1024 * 1024 * 1024,
    )

    print("\nBacktest Configuration:")
    print(f"  Strategy: {strategy_type}")
    print(f"  Instrument: {instrument}")
    print(f"  Date Range: {start_date} to {end_date}")
    print(f"  Initial Balance: ${config.initial_balance}")
    print(f"  Ticks: {len(tick_data)}")

    # Run backtest
    print("\nRunning backtest...")
    engine = BacktestEngine(config)
    trade_log, equity_curve, metrics = engine.run(tick_data)

    # Display results (same as mock data version)
    print("\n" + "=" * 70)
    print("BACKTEST RESULTS")
    print("=" * 70)
    print("\nPerformance Metrics:")
    print(f"  Total Trades:     {metrics['total_trades']}")
    print(f"  Win Rate:         {metrics['win_rate']:.2f}%")
    print(f"  Total Return:     {metrics['total_return']:.2f}%")
    print(f"  Final Balance:    ${metrics['final_balance']:.2f}")

    return trade_log, equity_curve, metrics


def run_backtest_with_athena_data() -> (
    tuple[list[BacktestTrade] | None, list[EquityPoint] | None, dict[str, Any] | None]
):
    """Run backtest with real Athena data.

    IMPORTANT: If you get "UnrecognizedClientException" errors, it means
    SystemSettings in the database has AWS access keys that are overriding
    your role credentials. To fix:
    1. Go to Django Admin → System Settings
    2. Clear aws_access_key_id and aws_secret_access_key fields
    3. Set aws_credential_method to "profile"
    4. Save and try again

    Or use the Django management command instead:
    python manage.py run_backtest --aws-role YOUR_ROLE_ARN ...
    """
    print("=" * 70)
    print("BACKTEST DEBUG - Athena Data")
    print("=" * 70)

    # Configuration - EDIT THESE VALUES
    instrument = "USD_JPY"
    start_date = datetime(2025, 11, 10)
    end_date = datetime(2025, 11, 11)
    strategy_type = "floor"
    strategy_config = {
        "instrument": instrument,
        "position_size": 1000,
    }

    # Athena configuration - EDIT THESE VALUES
    athena_database = "forex_hist_data_db"
    athena_table = "quotes"
    athena_bucket = "aws-athena-query-results-789121567207-us-west-2"  # CHANGE THIS!

    # AWS authentication - CHOOSE ONE METHOD:

    # Method 1: Use AWS Profile (recommended for local development)
    aws_profile = "auto-forex"  # Change to your profile name
    aws_region = "us-west-2"  # Change to your region
    aws_role_arn = "arn:aws:iam::789121567207:role/auto-forex-execution-role"

    # Method 2: Assume AWS Role (recommended for cross-account access)
    # aws_profile = None
    # aws_region = "us-east-1"
    # aws_role_arn = "arn:aws:iam::123456789012:role/BacktestRole"  # CHANGE THIS!

    # Method 3: Use environment variables (AWS_PROFILE, AWS_ROLE_ARN already set)
    # aws_profile = None
    # aws_region = None
    # aws_role_arn = None

    # Load real data from Athena
    tick_data = load_real_data_from_athena(
        instrument,
        start_date,
        end_date,
        athena_database,
        athena_table,
        athena_bucket,
        aws_profile=aws_profile,
        aws_role_arn=aws_role_arn,
        aws_region=aws_region,
    )

    if not tick_data:
        print("ERROR: No data found in Athena!")
        print("Check your Athena configuration and date range.")
        return None, None, None

    # Create backtest config
    config = BacktestConfig(
        strategy_type=strategy_type,
        strategy_config=strategy_config,
        instrument=instrument,
        start_date=start_date,
        end_date=end_date,
        initial_balance=Decimal("10000"),
        commission_per_trade=Decimal("0"),
        cpu_limit=1,
        memory_limit=32 * 1024 * 1024 * 1024,
    )

    print("\nBacktest Configuration:")
    print(f"  Strategy: {strategy_type}")
    print(f"  Instrument: {instrument}")
    print(f"  Date Range: {start_date} to {end_date}")
    print(f"  Initial Balance: ${config.initial_balance}")
    print(f"  Ticks: {len(tick_data)}")

    # Run backtest
    print("\nRunning backtest...")
    engine = BacktestEngine(config)
    trade_log, equity_curve, metrics = engine.run(tick_data)

    # Display results
    print("\n" + "=" * 70)
    print("BACKTEST RESULTS")
    print("=" * 70)
    print("\nPerformance Metrics:")
    print(f"  Total Trades:     {metrics['total_trades']}")
    print(f"  Win Rate:         {metrics['win_rate']:.2f}%")
    print(f"  Total Return:     {metrics['total_return']:.2f}%")
    print(f"  Final Balance:    ${metrics['final_balance']:.2f}")

    return trade_log, equity_curve, metrics


def display_backtest_results(
    engine: BacktestEngine,
    trade_log: list[BacktestTrade],
    equity_curve: list[EquityPoint],
    metrics: dict[str, Any],
    tick_data: list[TickDataPoint],
) -> None:
    """
    Display comprehensive backtest results including open positions and P&L breakdown.

    Args:
        engine: BacktestEngine instance with positions
        trade_log: List of closed trades
        equity_curve: List of equity points
        metrics: Performance metrics dictionary
        tick_data: List of tick data (for calculating unrealized P&L)
    """
    # Calculate unrealized P&L from open positions
    unrealized_pnl = Decimal("0")
    if engine.positions and tick_data:
        last_tick = tick_data[-1]
        for position in engine.positions:
            if position.instrument == last_tick.instrument:
                current_price = last_tick.bid if position.direction == "long" else last_tick.ask
                unrealized_pnl += position.calculate_pnl(current_price)

    # Calculate realized P&L from closed trades
    realized_pnl = Decimal(str(sum(trade.pnl for trade in trade_log)))

    print("\n" + "=" * 70)
    print("BACKTEST RESULTS")
    print("=" * 70)

    # Position Summary
    print("\nPosition Summary:")
    print(f"  Open Positions:   {len(engine.positions)}")
    print(f"  Closed Trades:    {len(trade_log)}")
    print(f"  Realized P&L:     ${realized_pnl:.2f}")
    print(f"  Unrealized P&L:   ${unrealized_pnl:.2f}")
    print(f"  Total P&L:        ${realized_pnl + unrealized_pnl:.2f}")

    # Performance Metrics
    print("\nPerformance Metrics:")
    print(f"  Total Trades:     {metrics['total_trades']}")
    print(f"  Win Rate:         {metrics['win_rate']:.2f}%")
    print(f"  Total Return:     {metrics['total_return']:.2f}%")
    print(f"  Final Balance:    ${metrics['final_balance']:.2f}")

    # Open Positions Detail
    if engine.positions:
        print(f"\nOpen Positions ({len(engine.positions)}):")
        for i, pos in enumerate(engine.positions[:10], 1):  # Show first 10
            current_price = last_tick.bid if pos.direction == "long" else last_tick.ask
            pnl = pos.calculate_pnl(current_price)
            pnl_sign = "+" if pnl > 0 else ""
            sl_str = f"{pos.stop_loss:.5f}" if pos.stop_loss else "None"
            tp_str = f"{pos.take_profit:.5f}" if pos.take_profit else "None"
            pos_info = (
                f"  {i}. {pos.direction.upper():5} {pos.instrument} | "
                f"Entry: {pos.entry_price:.5f} | "
                f"Current: {current_price:.5f} | "
                f"SL: {sl_str} | TP: {tp_str} | "
                f"P&L: {pnl_sign}${pnl:.2f}"
            )
            print(pos_info)
        if len(engine.positions) > 10:
            print(f"  ... and {len(engine.positions) - 10} more positions")

    # Trade Log Summary
    if trade_log:
        print("\nClosed Trades Summary:")
        print(f"  Winning Trades:   {metrics['winning_trades']}")
        print(f"  Losing Trades:    {metrics['losing_trades']}")
        if metrics.get("average_win"):
            print(f"  Average Win:      ${metrics['average_win']:.2f}")
        if metrics.get("average_loss"):
            print(f"  Average Loss:     ${metrics['average_loss']:.2f}")
        if metrics.get("profit_factor"):
            print(f"  Profit Factor:    {metrics['profit_factor']:.2f}")

        print(f"\n  All Trades ({len(trade_log)}):")
        header = (
            f"  {'#':<4} {'Dir':<5} {'Instrument':<10} {'Entry':<12} "
            f"{'Exit':<12} {'Pips':<8} {'Duration':<10} {'P&L':<12} {'Reason':<20}"
        )
        print(header)
        separator = (
            f"  {'-'*4} {'-'*5} {'-'*10} {'-'*12} {'-'*12} " f"{'-'*8} {'-'*10} {'-'*12} {'-'*20}"
        )
        print(separator)

        for i, trade in enumerate(trade_log, 1):
            pnl_sign = "+" if trade.pnl > 0 else ""
            pip_diff = getattr(trade, "pip_diff", 0.0)
            pip_sign = "+" if pip_diff > 0 else ""
            duration_str = f"{int(trade.duration)}s"
            if trade.duration >= 3600:
                duration_str = f"{trade.duration/3600:.1f}h"
            elif trade.duration >= 60:
                duration_str = f"{trade.duration/60:.1f}m"

            reason_display = getattr(trade, "reason_display", trade.reason)

            trade_info = (
                f"  {i:<4} {trade.direction.upper():<5} {trade.instrument:<10} "
                f"{trade.entry_price:<12.5f} {trade.exit_price:<12.5f} "
                f"{pip_sign}{pip_diff:<7.1f} {duration_str:<10} "
                f"{pnl_sign}${trade.pnl:<11.2f} {reason_display:<20}"
            )
            print(trade_info)

        # Close Reason Breakdown
        print("\n  Close Reason Breakdown:")
        reason_stats = {}
        for trade in trade_log:
            reason_display = getattr(trade, "reason_display", trade.reason)
            if reason_display not in reason_stats:
                reason_stats[reason_display] = {
                    "count": 0,
                    "total_pnl": 0.0,
                    "total_pips": 0.0,
                    "wins": 0,
                    "losses": 0,
                }
            reason_stats[reason_display]["count"] += 1
            reason_stats[reason_display]["total_pnl"] += trade.pnl
            pip_diff = getattr(trade, "pip_diff", 0.0)
            reason_stats[reason_display]["total_pips"] += pip_diff
            if trade.pnl > 0:
                reason_stats[reason_display]["wins"] += 1
            else:
                reason_stats[reason_display]["losses"] += 1

        # Sort by count (most common first)
        sorted_reasons = sorted(reason_stats.items(), key=lambda x: x[1]["count"], reverse=True)

        for reason, stats in sorted_reasons:
            win_rate = (stats["wins"] / stats["count"] * 100) if stats["count"] > 0 else 0
            avg_pnl = stats["total_pnl"] / stats["count"] if stats["count"] > 0 else 0
            avg_pips = stats["total_pips"] / stats["count"] if stats["count"] > 0 else 0
            pnl_sign = "+" if stats["total_pnl"] > 0 else ""
            pips_sign = "+" if avg_pips > 0 else ""

            reason_info = (
                f"    {reason:<20} | "
                f"Count: {stats['count']:<3} | "
                f"Win Rate: {win_rate:>5.1f}% | "
                f"Avg P&L: {pnl_sign}${avg_pnl:>7.2f} | "
                f"Avg Pips: {pips_sign}{avg_pips:>6.1f} | "
                f"Total P&L: {pnl_sign}${stats['total_pnl']:>8.2f}"
            )
            print(reason_info)

    # Equity Curve Summary
    if equity_curve:
        print("\nEquity Curve:")
        print(f"  Data Points:      {len(equity_curve)}")
        print(f"  Starting Equity:  ${equity_curve[0].balance:.2f}")
        print(f"  Ending Equity:    ${equity_curve[-1].balance:.2f}")
        if metrics.get("max_drawdown"):
            print(f"  Max Drawdown:     {metrics['max_drawdown']:.2f}%")

    print("\n" + "=" * 70)


def parse_datetime(date_str: str) -> datetime:
    """
    Parse date string with optional time component.

    Supports formats:
    - YYYY-MM-DD (time defaults to 00:00:00Z)
    - YYYY-MM-DDTHH:MM:SSZ (ISO 8601 format)
    - YYYY-MM-DD HH:MM:SS (legacy format, treated as UTC)

    Args:
        date_str: Date string to parse (assumed to be UTC)

    Returns:
        datetime object with UTC timezone
    """
    from datetime import timezone as dt_timezone

    # Try different formats
    formats = [
        "%Y-%m-%dT%H:%M:%SZ",  # ISO 8601: 2025-11-10T08:00:00Z
        "%Y-%m-%dT%H:%M:%S",  # ISO 8601 without Z: 2025-11-10T08:00:00
        "%Y-%m-%d %H:%M:%S",  # Legacy: 2025-11-10 08:00:00
        "%Y-%m-%d",  # Date only: 2025-11-10
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            # Make timezone-aware (UTC)
            return dt.replace(tzinfo=dt_timezone.utc)
        except ValueError:
            continue

    # If nothing worked, raise error
    raise ValueError(f"Invalid date format: {date_str}. " f"Use YYYY-MM-DD or YYYY-MM-DDTHH:MM:SSZ")


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Standalone backtest debugger with profiling support"
    )
    parser.add_argument(
        "--instrument",
        type=str,
        default="USD_JPY",
        help="Currency pair to backtest (default: JPY_USD)",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        required=True,
        help="Start date/time in YYYY-MM-DD or YYYY-MM-DDTHH:MM:SSZ format",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        required=True,
        help="End date/time in YYYY-MM-DD or YYYY-MM-DDTHH:MM:SSZ format",
    )
    parser.add_argument(
        "--data-source",
        type=str,
        choices=["mock", "postgres", "athena"],
        default="athena",
        help="Data source to use (default: athena)",
    )
    parser.add_argument(
        "--num-ticks",
        type=int,
        default=1000,
        help="Number of mock ticks to generate (only for mock data source, default: 1000)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_arguments()

    # =========================================================================
    # BACKTEST CONFIGURATION - Edit this section to customize your backtest
    # =========================================================================

    # Strategy Configuration
    STRATEGY_TYPE = "floor"
    STRATEGY_CONFIG = {
        # Position Sizing
        "base_lot_size": 1.0,  # Initial position size (1.0 = 1000 units)
        "scaling_mode": "additive",  # How to scale: "additive" or "multiplicative"
        "scaling_amount": 1.0,  # Amount to add (additive) or multiply by (multiplicative)
        # Entry/Exit Rules
        "retracement_pips": 25,  # Pips retracement needed to scale-in (add more positions)
        "take_profit_pips": 25,  # Pips profit to close positions
        "entry_signal_lookback_ticks": 10,  # Ticks to analyze for entry direction
        # Layer Management
        "max_layers": 10,  # Maximum concurrent layers
        "retracement_trigger_base": 10,  # Retracements before new layer
        # How triggers progress: equal, additive, exponential, inverse
        "retracement_trigger_progression": "additive",
        # Increment for layer triggers (Layer 1: 10, Layer 2: 15, Layer 3: 20)
        "retracement_trigger_increment": 10,
        # Lot Size Progression Across Layers
        # How lot sizes progress: equal, additive, exponential, inverse
        "lot_size_progression": "inverse",
        # Increment for lot sizes (Layer 1: 1.0, Layer 2: 2.0, Layer 3: 3.0)
        "lot_size_increment": 1,
        # Risk Management
        # ATR multiplier to trigger volatility lock (5x normal = lock)
        "volatility_lock_multiplier": 5.0,
    }

    # Backtest Parameters
    INITIAL_BALANCE = Decimal("10000")
    COMMISSION_PER_TRADE = Decimal("0")
    CPU_LIMIT = 1
    MEMORY_LIMIT = 32 * 1024 * 1024 * 1024  # 32 GB

    # Athena Configuration (for athena data source)
    ATHENA_DATABASE = "forex_hist_data_db"
    ATHENA_TABLE = "quotes"
    ATHENA_BUCKET = "aws-athena-query-results-789121567207-us-west-2"
    AWS_PROFILE = "auto-forex"
    AWS_REGION = "us-west-2"
    AWS_ROLE_ARN = "arn:aws:iam::789121567207:role/auto-forex-execution-role"

    # =========================================================================
    # END CONFIGURATION
    # =========================================================================

    print("\n" + "=" * 70)
    print("STANDALONE BACKTEST DEBUGGER")
    print("=" * 70)
    print("\nConfiguration:")
    print(f"  Instrument:   {args.instrument}")
    print(f"  Start Date:   {args.start_date}")
    print(f"  End Date:     {args.end_date}")
    print(f"  Data Source:  {args.data_source}")
    print(f"  Strategy:     {STRATEGY_TYPE}")
    if args.data_source == "mock":
        print(f"  Mock Ticks:   {args.num_ticks}")
    print("\nStrategy Parameters:")
    print(f"  Base Lot Size:            {STRATEGY_CONFIG['base_lot_size']}")
    print(f"  Scaling Mode:             {STRATEGY_CONFIG['scaling_mode']}")
    retr_pips = STRATEGY_CONFIG["retracement_pips"]
    print(f"  Retracement Pips:         {retr_pips} (to scale-in)")
    tp_pips = STRATEGY_CONFIG["take_profit_pips"]
    print(f"  Take Profit Pips:         {tp_pips} (to close)")
    print(f"  Max Layers:               {STRATEGY_CONFIG['max_layers']}")
    base_trigger = STRATEGY_CONFIG["retracement_trigger_base"]
    print(f"  Retracements per Layer:   {base_trigger} (Layer 1)")
    if STRATEGY_CONFIG["retracement_trigger_progression"] != "equal":
        retr_base = cast(int, STRATEGY_CONFIG["retracement_trigger_base"])
        retr_incr = cast(int, STRATEGY_CONFIG["retracement_trigger_increment"])
        layer2_trigger = retr_base + retr_incr
        layer3_trigger = layer2_trigger + retr_incr
        layer_info = (
            f"                            {layer2_trigger} (Layer 2), "
            f"{layer3_trigger} (Layer 3)"
        )
        print(layer_info)
    print("\nTo debug:")
    print("  1. Set breakpoints in this file or backtest_engine.py")
    print("  2. Run with debugger (F5 in VS Code)")
    print("  3. Or run directly: python debug_backtest.py")
    print("\n" + "=" * 70 + "\n")

    # Run backtest based on data source
    if args.data_source == "mock":
        instrument = args.instrument
        num_ticks = args.num_ticks

        print("=" * 70)
        print("BACKTEST DEBUG - Mock Data")
        print("=" * 70)

        tick_data = create_mock_tick_data(instrument, num_ticks=num_ticks)

        config = BacktestConfig(
            strategy_type=STRATEGY_TYPE,
            strategy_config=STRATEGY_CONFIG,
            instrument=instrument,
            start_date=tick_data[0].timestamp,
            end_date=tick_data[-1].timestamp,
            initial_balance=INITIAL_BALANCE,
            commission_per_trade=COMMISSION_PER_TRADE,
            cpu_limit=CPU_LIMIT,
            memory_limit=MEMORY_LIMIT,
        )

        print("\nBacktest Configuration:")
        print(f"  Strategy: {STRATEGY_TYPE}")
        print(f"  Instrument: {instrument}")
        print(f"  Initial Balance: ${config.initial_balance}")
        print(f"  Ticks: {len(tick_data)}")

        print("\nRunning backtest...")
        engine = BacktestEngine(config)

        def progress_callback(progress: int) -> None:
            if progress % 10 == 0:
                print(f"  Progress: {progress}%")

        engine.progress_callback = progress_callback
        trade_log, equity_curve, metrics = engine.run(tick_data)

        # Display comprehensive results
        display_backtest_results(engine, trade_log, equity_curve, metrics, tick_data)

    elif args.data_source == "postgres":
        instrument = args.instrument
        start_date = parse_datetime(args.start_date)
        end_date = parse_datetime(args.end_date)

        print("=" * 70)
        print("BACKTEST DEBUG - PostgreSQL Data")
        print("=" * 70)

        tick_data = load_real_data_from_postgres(instrument, start_date, end_date)

        if not tick_data:
            print("ERROR: No data found in PostgreSQL!")
            print("Try using mock data instead: --data-source mock")
            sys.exit(1)

        config = BacktestConfig(
            strategy_type=STRATEGY_TYPE,
            strategy_config=STRATEGY_CONFIG,
            instrument=instrument,
            start_date=start_date,
            end_date=end_date,
            initial_balance=INITIAL_BALANCE,
            commission_per_trade=COMMISSION_PER_TRADE,
            cpu_limit=CPU_LIMIT,
            memory_limit=MEMORY_LIMIT,
        )

        print("\nBacktest Configuration:")
        print(f"  Strategy: {STRATEGY_TYPE}")
        print(f"  Instrument: {instrument}")
        print(f"  Date Range: {start_date} to {end_date}")
        print(f"  Initial Balance: ${config.initial_balance}")
        print(f"  Ticks: {len(tick_data)}")

        print("\nRunning backtest...")
        engine = BacktestEngine(config)
        trade_log, equity_curve, metrics = engine.run(tick_data)

        # Display comprehensive results
        display_backtest_results(engine, trade_log, equity_curve, metrics, tick_data)

    else:  # athena
        instrument = args.instrument
        start_date = parse_datetime(args.start_date)
        end_date = parse_datetime(args.end_date)

        print("=" * 70)
        print("BACKTEST DEBUG - Athena Data")
        print("=" * 70)

        tick_data = load_real_data_from_athena(
            instrument,
            start_date,
            end_date,
            ATHENA_DATABASE,
            ATHENA_TABLE,
            ATHENA_BUCKET,
            aws_profile=AWS_PROFILE,
            aws_role_arn=AWS_ROLE_ARN,
            aws_region=AWS_REGION,
        )

        if not tick_data:
            print("ERROR: No data found in Athena!")
            print("Check your Athena configuration and date range.")
            sys.exit(1)

        config = BacktestConfig(
            strategy_type=STRATEGY_TYPE,
            strategy_config=STRATEGY_CONFIG,
            instrument=instrument,
            start_date=start_date,
            end_date=end_date,
            initial_balance=INITIAL_BALANCE,
            commission_per_trade=COMMISSION_PER_TRADE,
            cpu_limit=CPU_LIMIT,
            memory_limit=MEMORY_LIMIT,
        )

        print("\nBacktest Configuration:")
        print(f"  Strategy: {STRATEGY_TYPE}")
        print(f"  Instrument: {instrument}")
        print(f"  Date Range: {start_date} to {end_date}")
        print(f"  Initial Balance: ${config.initial_balance}")
        print(f"  Ticks: {len(tick_data)}")

        print("\nRunning backtest...")
        print("  This may take a while for large datasets...")
        print("  Progress updates every 10,000 ticks")
        engine = BacktestEngine(config)
        trade_log, equity_curve, metrics = engine.run(tick_data)

        # Display comprehensive results
        display_backtest_results(engine, trade_log, equity_curve, metrics, tick_data)

    print("\nDone! Set breakpoints and run with debugger to step through the code.")
