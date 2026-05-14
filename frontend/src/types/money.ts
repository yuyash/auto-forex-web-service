export interface MoneyAmount {
  amount: string;
  currency: string;
}

export interface MoneyAmountLike {
  amount?: string | number | null;
  currency?: string | null;
}

export type TaskMoneyCurrencySource =
  | 'backtest_task'
  | 'task_display_currency'
  | 'account_currency'
  | 'oanda_account'
  | 'unknown';

export type TaskMoneyConversionPolicy =
  | 'identity'
  | 'runtime_fx_rate'
  | 'unavailable';

export interface TaskMoneyContext {
  task_type: 'backtest' | 'trading';
  account_currency: string;
  account_currency_source: TaskMoneyCurrencySource;
  display_currency: string;
  display_currency_source: TaskMoneyCurrencySource;
  initial_balance_money?: MoneyAmount | null;
  commission_per_trade_money?: MoneyAmount | null;
  display_uses_account_currency: boolean;
  display_requires_conversion: boolean;
  conversion_policy: TaskMoneyConversionPolicy;
}

export interface CurrencyConversionContext {
  source_currency: string;
  target_currency: string;
  rate?: string | number | null;
  rate_source: string;
  rate_as_of?: string | null;
  rate_path: string[];
  conversion_available: boolean;
  conversion_policy: TaskMoneyConversionPolicy;
}
