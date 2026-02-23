/**
 * API types — hand-maintained replacements for the previously generated models.
 */

// --- Enums ---

export enum StatusEnum {
  CREATED = 'created',
  STARTING = 'starting',
  RUNNING = 'running',
  PAUSED = 'paused',
  STOPPING = 'stopping',
  STOPPED = 'stopped',
  COMPLETED = 'completed',
  FAILED = 'failed',
}

export enum DataSourceEnum {
  POSTGRESQL = 'postgresql',
  ATHENA = 'athena',
  S3 = 's3',
}

export enum ApiTypeEnum {
  PRACTICE = 'practice',
  LIVE = 'live',
}

export enum JurisdictionEnum {
  US = 'US',
  JP = 'JP',
  OTHER = 'OTHER',
}

// --- OANDA Account types ---

export interface OandaAccounts {
  readonly id?: number;
  account_id: string;
  api_type?: ApiTypeEnum;
  jurisdiction?: JurisdictionEnum;
  currency?: string;
  readonly balance?: string;
  readonly margin_used?: string;
  readonly margin_available?: string;
  readonly unrealized_pnl?: string;
  is_active?: boolean;
  is_default?: boolean;
  readonly created_at?: string;
  readonly updated_at?: string;
}

export interface OandaAccountsRequest {
  account_id: string;
  api_token: string;
  api_type?: ApiTypeEnum;
  jurisdiction?: JurisdictionEnum;
  currency?: string;
  is_active?: boolean;
  is_default?: boolean;
}

// --- Trading Task types ---

export interface TradingTaskRequest {
  name: string;
  config: number | string;
  oanda_account: number | string;
  description?: string;
  sell_on_stop?: boolean;
}

export interface PatchedTradingTaskCreateRequest {
  name?: string;
  config?: number | string;
  oanda_account?: number | string;
  description?: string;
  sell_on_stop?: boolean;
}

// --- Backtest Task types ---

export interface BacktestTaskRequest {
  name: string;
  config: number | string;
  start_time: string;
  end_time: string;
  description?: string;
  data_source?: DataSourceEnum;
  initial_balance?: string;
  commission_per_trade?: string;
  instrument?: string;
}

export interface PatchedBacktestTaskCreateRequest {
  name?: string;
  config?: number | string;
  start_time?: string;
  end_time?: string;
  description?: string;
  data_source?: DataSourceEnum;
  initial_balance?: string;
  commission_per_trade?: string;
  instrument?: string;
}

// --- Strategy Config types ---

export interface StrategyConfigCreateRequest {
  name: string;
  strategy_id: string;
  parameters?: Record<string, unknown>;
  description?: string;
}

// --- Paginated response (generic) ---

export interface PaginatedApiResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}
