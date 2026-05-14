// Backtest types
import type { CurrencyConversionContext, MoneyAmount } from './money';

export interface BacktestResult {
  id: number;
  backtest: number;
  final_balance: number;
  total_return: number;
  max_drawdown: number;
  sharpe_ratio: number;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate: number;
  average_win: number;
  average_loss: number;
  profit_factor: number;
  final_balance_money?: MoneyAmount;
  final_balance_display_money?: MoneyAmount | null;
  display_conversion_context?: CurrencyConversionContext | null;
  equity_curve: Array<{
    timestamp: string;
    balance: number;
    balance_money?: MoneyAmount;
    balance_display_money?: MoneyAmount | null;
    display_conversion_context?: CurrencyConversionContext | null;
  }>;
  trade_log: Array<{
    timestamp: string;
    instrument: string;
    direction: string;
    entry_price: number;
    exit_price: number;
    units: number;
    pnl: number;
    pnl_money?: MoneyAmount;
    pnl_display_money?: MoneyAmount | null;
    display_conversion_context?: CurrencyConversionContext | null;
    duration: number;
  }>;
}

export interface BacktestConfig {
  strategy_type: string;
  config: Record<string, unknown>;
  instrument: string;
  data_source: string;
  start_date: string;
  end_date: string;
  initial_balance: number;
  account_currency?: string;
  display_currency?: string;
  initial_balance_money?: MoneyAmount;
  commission: number;
}

export interface Backtest {
  id: number;
  user: number;
  strategy_type: string;
  config: Record<string, unknown>;
  instrument: string;
  data_source: string;
  start_date: string;
  end_date: string;
  initial_balance: number;
  account_currency?: string;
  display_currency?: string;
  initial_balance_money?: MoneyAmount;
  status: 'pending' | 'running' | 'completed' | 'failed';
  progress: number;
  created_at: string;
  completed_at: string | null;
}
