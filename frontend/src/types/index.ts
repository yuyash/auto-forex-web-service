// Export all types
export * from './auth';
export * from './backtest';
export * from './chart';

// Export specific types from admin to avoid conflicts with auth
export type {
  SystemHealth,
  UserSession,
  RunningStrategy,
  AdminEvent,
  AdminDashboardData,
  AdminNotification,
} from './admin';

// Export specific types from order to avoid conflicts with chart
export type { OrderFilters, OrdersResponse } from './order';

// Export specific types from position to avoid conflicts with chart
export type { PositionFilters, PositionsResponse } from './position';

// Export specific types from strategy to avoid conflicts with configuration
export type {
  Strategy,
  ConfigSchema,
  ConfigProperty,
  StrategyStatus,
  StrategyStartRequest,
  StrategyPerformance,
  Account,
  PositionDifferentiationSettings,
} from './strategy';

// New task-based types
export * from './common';
export * from './configuration';
export * from './backtestTask';
export * from './tradingTask';
export * from './execution';

// Export StrategyEvent explicitly for clarity
export type { StrategyEvent } from './execution';

// Re-export the primary versions of conflicting types
export type { User, SystemSettings } from './auth';
export type { Order } from './order';
export type { Position } from './position';
export type { StrategyConfig } from './configuration';
