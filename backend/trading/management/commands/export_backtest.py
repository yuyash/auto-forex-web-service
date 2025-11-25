"""
Management command to export backtest results as JSON.

Usage:
    python manage.py export_backtest <backtest_id>
    python manage.py export_backtest <backtest_id> --output results.json
"""

import json
import sys
from decimal import Decimal
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from trading.backtest_models import Backtest


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder that handles Decimal types."""

    def default(self, o: Any) -> Any:  # pylint: disable=method-hidden
        if isinstance(o, Decimal):
            return float(o)
        return super().default(o)


class Command(BaseCommand):
    """Export backtest results to JSON format."""

    help = "Export backtest results including trades, metrics, and floor/layer data to JSON"

    def add_arguments(self, parser: Any) -> None:
        """Add command arguments."""
        parser.add_argument(
            "backtest_id",
            type=int,
            help="ID of the backtest to export",
        )
        parser.add_argument(
            "--output",
            "-o",
            type=str,
            help="Output file path (default: stdout)",
        )
        parser.add_argument(
            "--pretty",
            action="store_true",
            help="Pretty-print JSON output",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """Execute the command."""
        backtest_id = options["backtest_id"]
        output_file = options.get("output")
        pretty = options.get("pretty", False)

        try:
            backtest = Backtest.objects.select_related("result").get(id=backtest_id)
        except Backtest.DoesNotExist as exc:
            raise CommandError(f"Backtest with ID {backtest_id} does not exist") from exc

        # Build export data
        export_data = {
            "backtest_id": backtest.pk,
            "strategy_type": backtest.strategy_type,
            "instrument": backtest.instrument,
            "start_date": backtest.start_date.isoformat(),
            "end_date": backtest.end_date.isoformat(),
            "initial_balance": float(backtest.initial_balance),
            "commission_per_trade": float(backtest.commission_per_trade),
            "status": backtest.status,
            "config": backtest.config,
            # Performance metrics
            "metrics": {
                "total_trades": backtest.total_trades,
                "winning_trades": backtest.winning_trades,
                "losing_trades": backtest.losing_trades,
                "win_rate": float(backtest.win_rate),
                "total_return": float(backtest.total_return),
                "final_balance": float(backtest.final_balance) if backtest.final_balance else None,
            },
            # Trade log with floor/layer information
            "trade_log": backtest.trade_log,
            # Equity curve
            "equity_curve": backtest.equity_curve,
            # Execution details
            "execution": {
                "started_at": backtest.started_at.isoformat() if backtest.started_at else None,
                "completed_at": (
                    backtest.completed_at.isoformat() if backtest.completed_at else None
                ),
                "duration": backtest.duration,
                "peak_memory_mb": (
                    float(backtest.peak_memory_mb) if backtest.peak_memory_mb else None
                ),
                "memory_limit_mb": (
                    float(backtest.memory_limit_mb) if backtest.memory_limit_mb else None
                ),
                "cpu_limit_cores": backtest.cpu_limit_cores,
            },
        }

        # Add detailed result metrics if available
        if hasattr(backtest, "result") and backtest.result:
            result = backtest.result
            export_data["detailed_metrics"] = {
                "total_pnl": float(result.total_pnl),
                "max_drawdown": float(result.max_drawdown),
                "max_drawdown_amount": float(result.max_drawdown_amount),
                "sharpe_ratio": float(result.sharpe_ratio) if result.sharpe_ratio else None,
                "average_win": float(result.average_win),
                "average_loss": float(result.average_loss),
                "largest_win": float(result.largest_win),
                "largest_loss": float(result.largest_loss),
                "profit_factor": float(result.profit_factor) if result.profit_factor else None,
                "average_trade_duration": (
                    str(result.average_trade_duration) if result.average_trade_duration else None
                ),
            }

        # Serialize to JSON
        indent = 2 if pretty else None
        json_output = json.dumps(export_data, cls=DecimalEncoder, indent=indent)

        # Output to file or stdout
        if output_file:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(json_output)
            self.stdout.write(
                self.style.SUCCESS(f"Successfully exported backtest {backtest_id} to {output_file}")
            )
        else:
            sys.stdout.write(json_output)
            sys.stdout.write("\n")
