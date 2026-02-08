"""Candle data management for Floor strategy."""

from datetime import datetime
from decimal import Decimal

from apps.trading.strategies.floor.models import CandleData, FloorStrategyConfig, FloorStrategyState


class CandleManager:
    """Manage candle data for trend detection."""

    def __init__(self, config: FloorStrategyConfig) -> None:
        """Initialize candle manager.

        Args:
            config: Strategy configuration
        """
        self.config = config

    def update_from_tick(
        self,
        state: FloorStrategyState,
        timestamp: datetime,
        mid_price: Decimal,
    ) -> None:
        """Update candle data from tick.

        Args:
            state: Strategy state
            timestamp: Tick timestamp
            mid_price: Mid price
        """
        bucket_start = self._get_bucket_start(timestamp)

        # 初回または新しいキャンドル
        if not state.candles or state.candles[-1].bucket_start_epoch != bucket_start:
            # 前のキャンドルを確定
            if state.current_candle_close is not None:
                candle = CandleData(
                    bucket_start_epoch=state.candles[-1].bucket_start_epoch
                    if state.candles
                    else bucket_start,
                    close_price=state.current_candle_close,
                )
                if (
                    state.candles
                    and state.candles[-1].bucket_start_epoch == candle.bucket_start_epoch
                ):
                    state.candles[-1] = candle
                else:
                    state.candles.append(candle)

            # 新しいキャンドル開始
            state.current_candle_close = mid_price

            # 履歴を制限
            max_candles = self.config.candle_lookback_count + 5
            if len(state.candles) > max_candles:
                state.candles = state.candles[-max_candles:]
        else:
            # 同じキャンドル内 - closeを更新
            state.current_candle_close = mid_price

    def _get_bucket_start(self, timestamp: datetime) -> int:
        """Get candle bucket start epoch.

        Args:
            timestamp: Timestamp

        Returns:
            Bucket start epoch in seconds
        """
        epoch = int(timestamp.timestamp())
        granularity = self.config.candle_granularity_seconds
        return epoch - (epoch % granularity)

    def get_candle_closes(self, state: FloorStrategyState) -> list[Decimal]:
        """Get list of candle close prices including current.

        Args:
            state: Strategy state

        Returns:
            List of close prices
        """
        closes = [c.close_price for c in state.candles]

        # 現在のキャンドルを含める
        if state.current_candle_close is not None:
            closes.append(state.current_candle_close)

        return closes

    def has_enough_candles(self, state: FloorStrategyState) -> bool:
        """Check if enough candles for trend detection.

        Args:
            state: Strategy state

        Returns:
            True if enough candles
        """
        closes = self.get_candle_closes(state)
        return len(closes) >= self.config.candle_lookback_count
