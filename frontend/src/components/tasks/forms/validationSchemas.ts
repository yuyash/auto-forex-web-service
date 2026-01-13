import { z } from 'zod';
import { DataSource } from '../../../types/common';

// Data source values array for Zod validation
const dataSourceValues = [
  DataSource.POSTGRESQL,
  DataSource.ATHENA,
  DataSource.S3,
] as const;

// Configuration validation schema
export const configurationSchema = z.object({
  name: z
    .string()
    .min(1, 'Name is required')
    .max(255, 'Name must be less than 255 characters'),
  strategy_type: z.string().min(1, 'Strategy type is required'),
  parameters: z.record(z.string(), z.unknown()),
  description: z.string().optional(),
});

// Backtest task validation schema
export const backtestTaskSchema = z
  .object({
    config_id: z.coerce
      .number({
        message: 'Configuration must be a number',
      })
      .positive('Configuration is required'),
    name: z
      .string()
      .min(1, 'Name is required')
      .max(255, 'Name must be less than 255 characters'),
    description: z.string().optional(),
    data_source: z.enum(dataSourceValues),
    start_time: z.string().min(1, 'Start date is required'),
    end_time: z.string().min(1, 'End date is required'),
    initial_balance: z.coerce
      .number({
        message: 'Initial balance must be a number',
      })
      .positive('Initial balance must be greater than zero'),
    commission_per_trade: z.coerce
      .number({
        message: 'Commission must be a number',
      })
      .nonnegative('Commission cannot be negative')
      .optional(),
    pip_size: z.coerce
      .number({
        message: 'Pip size must be a number',
      })
      .positive('Pip size must be greater than zero')
      .optional(),
    instrument: z
      .string()
      .min(1, 'Instrument is required')
      .max(20, 'Instrument must be less than 20 characters'),
    trading_mode: z.enum(['netting', 'hedging']).optional().default('netting'),
    sell_at_completion: z.boolean().optional().default(false),
  })
  .refine((data) => data.start_time < data.end_time, {
    message: 'Start date must be before end date',
    path: ['start_time'],
  });

// Trading task validation schema
export const tradingTaskSchema = z.object({
  config_id: z.number().positive('Configuration is required'),
  oanda_account_id: z.number().positive('Account is required'),
  name: z
    .string()
    .min(1, 'Name is required')
    .max(255, 'Name must be less than 255 characters'),
  description: z.string().optional(),
  sell_on_stop: z.boolean().optional().default(false),
});

// Copy task validation schema
export const copyTaskSchema = z.object({
  new_name: z
    .string()
    .min(1, 'Name is required')
    .max(255, 'Name must be less than 255 characters'),
});

// Date range validation helper
export const validateDateRange = (
  startDate: Date | null,
  endDate: Date | null,
  required: boolean = false
): { isValid: boolean; error?: string } => {
  if (required && (!startDate || !endDate)) {
    return { isValid: false, error: 'Both start and end dates are required' };
  }

  if (startDate && endDate && startDate >= endDate) {
    return { isValid: false, error: 'Start date must be before end date' };
  }

  return { isValid: true };
};

// Balance validation helper
export const validateBalance = (
  value: string | number,
  min: number = 0,
  max?: number
): { isValid: boolean; error?: string } => {
  const numValue = typeof value === 'string' ? parseFloat(value) : value;

  if (isNaN(numValue)) {
    return { isValid: false, error: 'Please enter a valid number' };
  }

  if (numValue <= min) {
    return { isValid: false, error: `Balance must be greater than ${min}` };
  }

  if (max !== undefined && numValue > max) {
    return { isValid: false, error: `Balance must not exceed ${max}` };
  }

  return { isValid: true };
};

// Instrument validation helper
export const validateInstrument = (
  instrument: string,
  min: number = 1,
  max?: number
): { isValid: boolean; error?: string } => {
  if (instrument.length < min) {
    return {
      isValid: false,
      error: `At least ${min} instrument${min > 1 ? 's' : ''} required`,
    };
  }

  if (max !== undefined && instrument.length > max) {
    return {
      isValid: false,
      error: `Maximum ${max} instrument${max > 1 ? 's' : ''} allowed`,
    };
  }

  return { isValid: true };
};

// Export types inferred from schemas
export type ConfigurationFormData = z.infer<typeof configurationSchema>;
// Explicitly define the output type since z.coerce doesn't infer properly
export type BacktestTaskSchemaOutput = {
  config_id: number;
  name: string;
  description?: string;
  data_source: DataSource;
  start_time: string;
  end_time: string;
  initial_balance: number;
  commission_per_trade?: number;
  pip_size?: number;
  instrument: string;
  trading_mode?: 'netting' | 'hedging';
  sell_at_completion?: boolean;
};
export type TradingTaskFormData = z.infer<typeof tradingTaskSchema>;
export type CopyTaskFormData = z.infer<typeof copyTaskSchema>;
