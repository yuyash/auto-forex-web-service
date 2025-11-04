// Backtest types
export interface Backtest {
  id: number;
  user: number;
  strategy_type: string;
  config: Record<string, unknown>;
  instruments: string[];
  start_date: string;
  end_date: string;
  initial_balance: number;
  status: 'pending' | 'running' | 'completed' | 'failed';
  progress: number;
  created_at: string;
  completed_at: string | null;
}

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
  equity_curve: Array<{ timestamp: string; balance: number }>;
  trade_log: Array<{
    timestamp: string;
    instrument: string;
    direction: string;
    entry_price: number;
    exit_price: number;
    units: number;
    pnl: number;
    duration: number;
  }>;
}

export interface BacktestConfig {
  strategy_type: string;
  config: Record<string, unknown>;
  instruments: string[];
  start_date: string;
  end_date: string;
  initial_balance: number;
  slippage: number;
  commission: number;
}
