"""
Parallel strategy execution and comparison engine.

This module provides functionality to:
- Run multiple strategies concurrently with isolation
- Compare performance metrics across strategies
- Generate comparison reports

Requirements: 5.1, 5.3, 12.4
"""

import logging
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from trading.backtest_engine import BacktestConfig, BacktestEngine
from trading.historical_data_loader import TickDataPoint

logger = logging.getLogger(__name__)


@dataclass
class StrategyComparisonConfig:
    """
    Configuration for strategy comparison.

    Attributes:
        strategy_configs: List of strategy configurations to compare
        instruments: List of currency pairs
        start_date: Start date for comparison period
        end_date: End date for comparison period
        initial_balance: Initial account balance
        slippage_pips: Slippage in pips
        commission_per_trade: Commission per trade
        max_workers: Maximum number of parallel workers (default: 10)
    """

    strategy_configs: list[dict[str, Any]]
    instruments: list[str]
    start_date: datetime
    end_date: datetime
    initial_balance: Decimal
    slippage_pips: Decimal = Decimal("0")
    commission_per_trade: Decimal = Decimal("0")
    max_workers: int = 10


def _run_single_strategy(
    strategy_config: dict[str, Any],
    tick_data: list[dict[str, Any]],
    backtest_config_dict: dict[str, Any],
) -> dict[str, Any]:
    """
    Run a single strategy in isolated process.

    This function is designed to be executed in a separate process
    to ensure complete isolation between strategy executions.

    Args:
        strategy_config: Strategy configuration
        tick_data: Historical tick data as list of dicts
        backtest_config_dict: Backtest configuration as dict

    Returns:
        Dictionary with strategy results
    """
    try:
        # Convert tick data dicts back to TickDataPoint objects
        tick_data_points = [
            TickDataPoint(
                instrument=t["instrument"],
                timestamp=datetime.fromisoformat(t["timestamp"]),
                bid=Decimal(str(t["bid"])),
                ask=Decimal(str(t["ask"])),
                mid=Decimal(str(t["mid"])),
                spread=Decimal(str(t["spread"])),
            )
            for t in tick_data
        ]

        # Create backtest config
        config = BacktestConfig(
            strategy_type=strategy_config["strategy_type"],
            strategy_config=strategy_config["config"],
            instruments=backtest_config_dict["instruments"],
            start_date=datetime.fromisoformat(backtest_config_dict["start_date"]),
            end_date=datetime.fromisoformat(backtest_config_dict["end_date"]),
            initial_balance=Decimal(str(backtest_config_dict["initial_balance"])),
            slippage_pips=Decimal(str(backtest_config_dict["slippage_pips"])),
            commission_per_trade=Decimal(str(backtest_config_dict["commission_per_trade"])),
            cpu_limit=backtest_config_dict.get("cpu_limit", 1),
            memory_limit=backtest_config_dict.get("memory_limit", 2147483648),
        )

        # Run backtest
        engine = BacktestEngine(config)
        trade_log, equity_curve, performance_metrics = engine.run(tick_data_points)

        return {
            "strategy_type": strategy_config["strategy_type"],
            "strategy_name": strategy_config.get("name", strategy_config["strategy_type"]),
            "config": strategy_config["config"],
            "trade_log": trade_log,
            "equity_curve": equity_curve,
            "performance_metrics": performance_metrics,
            "success": True,
            "error": None,
        }

    except Exception as e:
        logger.error(f"Strategy execution failed: {e}", exc_info=True)
        return {
            "strategy_type": strategy_config.get("strategy_type", "unknown"),
            "strategy_name": strategy_config.get("name", "unknown"),
            "config": strategy_config.get("config", {}),
            "trade_log": [],
            "equity_curve": [],
            "performance_metrics": {},
            "success": False,
            "error": str(e),
        }


class ParallelStrategyExecutor:
    """
    Execute multiple strategies concurrently with isolation.

    This class runs multiple strategies in parallel using separate processes
    to ensure complete isolation and prevent shared state issues.

    Requirements: 5.1, 5.3
    """

    def __init__(self, config: StrategyComparisonConfig):
        """
        Initialize ParallelStrategyExecutor.

        Args:
            config: Strategy comparison configuration
        """
        self.config = config
        self.max_workers = min(config.max_workers, 10)  # Enforce max 10 workers

    def execute_strategies(self, tick_data: list[TickDataPoint]) -> list[dict[str, Any]]:
        """
        Execute all strategies in parallel.

        Args:
            tick_data: Historical tick data

        Returns:
            List of strategy results

        Raises:
            ValueError: If more than 10 strategies provided
        """
        if len(self.config.strategy_configs) > 10:
            raise ValueError(
                f"Maximum 10 strategies allowed, got {len(self.config.strategy_configs)}"
            )

        logger.info(
            f"Starting parallel execution of {len(self.config.strategy_configs)} strategies"
        )

        # Convert tick data to serializable format for multiprocessing
        tick_data_dicts = [
            {
                "instrument": t.instrument,
                "timestamp": t.timestamp.isoformat(),
                "bid": float(t.bid),
                "ask": float(t.ask),
                "mid": float(t.mid),
                "spread": float(t.spread),
            }
            for t in tick_data
        ]

        # Prepare backtest config dict
        backtest_config_dict = {
            "instruments": self.config.instruments,
            "start_date": self.config.start_date.isoformat(),
            "end_date": self.config.end_date.isoformat(),
            "initial_balance": float(self.config.initial_balance),
            "slippage_pips": float(self.config.slippage_pips),
            "commission_per_trade": float(self.config.commission_per_trade),
            "cpu_limit": 1,
            "memory_limit": 2147483648,
        }

        results = []

        # Execute strategies in parallel using ProcessPoolExecutor
        with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all strategy executions
            future_to_strategy = {
                executor.submit(
                    _run_single_strategy,
                    strategy_config,
                    tick_data_dicts,
                    backtest_config_dict,
                ): strategy_config
                for strategy_config in self.config.strategy_configs
            }

            # Collect results as they complete
            for future in as_completed(future_to_strategy):
                strategy_config = future_to_strategy[future]
                try:
                    result = future.result()
                    results.append(result)
                    logger.info(
                        f"Strategy completed: {result['strategy_name']} "
                        f"(success={result['success']})"
                    )
                except Exception as e:
                    logger.error(
                        f"Strategy execution failed: {strategy_config.get('name', 'unknown')} - {e}"
                    )
                    results.append(
                        {
                            "strategy_type": strategy_config.get("strategy_type", "unknown"),
                            "strategy_name": strategy_config.get("name", "unknown"),
                            "config": strategy_config.get("config", {}),
                            "trade_log": [],
                            "equity_curve": [],
                            "performance_metrics": {},
                            "success": False,
                            "error": str(e),
                        }
                    )

        logger.info(
            f"Parallel execution completed: {len(results)} strategies, "
            f"{sum(1 for r in results if r['success'])} successful"
        )

        return results


class StrategyComparisonEngine:
    """
    Compare performance metrics across multiple strategies.

    This class analyzes strategy results and generates comparison reports
    with metrics tables and overlaid equity curves.

    Requirements: 5.1, 5.3, 12.4
    """

    def __init__(self, strategy_results: list[dict[str, Any]]):
        """
        Initialize StrategyComparisonEngine.

        Args:
            strategy_results: List of strategy execution results
        """
        self.strategy_results = strategy_results

    def generate_comparison_report(self) -> dict[str, Any]:
        """
        Generate comprehensive comparison report.

        Returns:
            Dictionary containing:
            - metrics_table: Comparison of key metrics across strategies
            - equity_curves: Overlaid equity curves for visualization
            - rankings: Strategies ranked by various metrics
            - summary: Overall comparison summary
        """
        logger.info(f"Generating comparison report for {len(self.strategy_results)} strategies")

        # Extract metrics for comparison
        metrics_table = self._build_metrics_table()

        # Prepare equity curves for overlay
        equity_curves = self._prepare_equity_curves()

        # Rank strategies by different metrics
        rankings = self._calculate_rankings()

        # Generate summary
        summary = self._generate_summary()

        report = {
            "metrics_table": metrics_table,
            "equity_curves": equity_curves,
            "rankings": rankings,
            "summary": summary,
            "total_strategies": len(self.strategy_results),
            "successful_strategies": sum(1 for r in self.strategy_results if r["success"]),
            "failed_strategies": sum(1 for r in self.strategy_results if not r["success"]),
        }

        logger.info("Comparison report generated successfully")

        return report

    def _build_metrics_table(self) -> list[dict[str, Any]]:
        """
        Build metrics comparison table.

        Returns:
            List of metric rows for each strategy
        """
        metrics_table = []

        for result in self.strategy_results:
            if not result["success"]:
                # Add row for failed strategy
                metrics_table.append(
                    {
                        "strategy_name": result["strategy_name"],
                        "strategy_type": result["strategy_type"],
                        "success": False,
                        "error": result["error"],
                        "total_return": None,
                        "total_trades": None,
                        "win_rate": None,
                        "sharpe_ratio": None,
                        "max_drawdown": None,
                        "profit_factor": None,
                    }
                )
                continue

            metrics = result["performance_metrics"]
            metrics_table.append(
                {
                    "strategy_name": result["strategy_name"],
                    "strategy_type": result["strategy_type"],
                    "success": True,
                    "error": None,
                    "total_return": metrics.get("total_return"),
                    "total_trades": metrics.get("total_trades"),
                    "win_rate": metrics.get("win_rate"),
                    "sharpe_ratio": metrics.get("sharpe_ratio"),
                    "max_drawdown": metrics.get("max_drawdown"),
                    "profit_factor": metrics.get("profit_factor"),
                    "final_balance": metrics.get("final_balance"),
                    "winning_trades": metrics.get("winning_trades"),
                    "losing_trades": metrics.get("losing_trades"),
                    "average_win": metrics.get("average_win"),
                    "average_loss": metrics.get("average_loss"),
                }
            )

        return metrics_table

    def _prepare_equity_curves(self) -> dict[str, list[dict[str, Any]]]:
        """
        Prepare equity curves for overlay visualization.

        Returns:
            Dictionary mapping strategy names to equity curve data
        """
        equity_curves = {}

        for result in self.strategy_results:
            if result["success"] and result["equity_curve"]:
                equity_curves[result["strategy_name"]] = result["equity_curve"]

        return equity_curves

    def _calculate_rankings(self) -> dict[str, list[dict[str, Any]]]:
        """
        Rank strategies by various metrics.

        Returns:
            Dictionary with rankings by different metrics
        """
        successful_results = [r for r in self.strategy_results if r["success"]]

        # Rank by total return
        by_total_return = sorted(
            [
                {
                    "strategy_name": r["strategy_name"],
                    "value": r["performance_metrics"].get("total_return", 0),
                }
                for r in successful_results
            ],
            key=lambda x: x["value"],
            reverse=True,
        )

        # Rank by Sharpe ratio
        by_sharpe_ratio = sorted(
            [
                {
                    "strategy_name": r["strategy_name"],
                    "value": r["performance_metrics"].get("sharpe_ratio"),
                }
                for r in successful_results
                if r["performance_metrics"].get("sharpe_ratio") is not None
            ],
            key=lambda x: x["value"] if x["value"] is not None else float("-inf"),
            reverse=True,
        )

        # Rank by win rate
        by_win_rate = sorted(
            [
                {
                    "strategy_name": r["strategy_name"],
                    "value": r["performance_metrics"].get("win_rate", 0),
                }
                for r in successful_results
            ],
            key=lambda x: x["value"],
            reverse=True,
        )

        # Rank by max drawdown (lower is better)
        by_max_drawdown = sorted(
            [
                {
                    "strategy_name": r["strategy_name"],
                    "value": r["performance_metrics"].get("max_drawdown", 0),
                }
                for r in successful_results
            ],
            key=lambda x: x["value"],
            reverse=False,  # Lower drawdown is better
        )

        return {
            "by_total_return": by_total_return,
            "by_sharpe_ratio": by_sharpe_ratio,
            "by_win_rate": by_win_rate,
            "by_max_drawdown": by_max_drawdown,
        }

    def _generate_summary(self) -> dict[str, Any]:
        """
        Generate overall comparison summary.

        Returns:
            Summary statistics across all strategies
        """
        successful_results = [r for r in self.strategy_results if r["success"]]

        if not successful_results:
            return {
                "best_strategy": None,
                "worst_strategy": None,
                "average_return": 0.0,
                "average_win_rate": 0.0,
                "total_strategies_compared": len(self.strategy_results),
            }

        # Find best and worst by total return
        best_strategy = max(
            successful_results,
            key=lambda r: r["performance_metrics"].get("total_return", float("-inf")),
        )
        worst_strategy = min(
            successful_results,
            key=lambda r: r["performance_metrics"].get("total_return", float("inf")),
        )

        # Calculate averages
        total_returns = [
            r["performance_metrics"].get("total_return", 0) for r in successful_results
        ]
        win_rates = [r["performance_metrics"].get("win_rate", 0) for r in successful_results]

        return {
            "best_strategy": {
                "name": best_strategy["strategy_name"],
                "total_return": best_strategy["performance_metrics"].get("total_return"),
            },
            "worst_strategy": {
                "name": worst_strategy["strategy_name"],
                "total_return": worst_strategy["performance_metrics"].get("total_return"),
            },
            "average_return": sum(total_returns) / len(total_returns) if total_returns else 0.0,
            "average_win_rate": sum(win_rates) / len(win_rates) if win_rates else 0.0,
            "total_strategies_compared": len(self.strategy_results),
            "successful_strategies": len(successful_results),
        }
