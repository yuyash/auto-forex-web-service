import { z } from 'zod';
import { DataSource } from '../../../types/common';

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
    config_id: z.number().positive('Configuration is required'),
    name: z
      .string()
      .min(1, 'Name is required')
      .max(255, 'Name must be less than 255 characters'),
    description: z.string().optional(),
    data_source: z.nativeEnum(DataSource),
    start_time: z.string().min(1, 'Start date is required'),
    end_time: z.string().min(1, 'End date is required'),
    initial_balance: z
      .number()
      .positive('Initial balance must be greater than zero')
      .or(z.string().regex(/^\d+\.?\d*$/, 'Invalid balance format')),
    commission_per_trade: z
      .number()
      .nonnegative('Commission cannot be negative')
      .optional()
      .or(
        z
          .string()
          .regex(/^\d+\.?\d*$/, 'Invalid commission format')
          .optional()
      ),
    instruments: z
      .array(z.string())
      .min(1, 'At least one instrument is required')
      .max(20, 'Maximum 20 instruments allowed'),
  })
  .refine((data) => data.start_time < data.end_time, {
    message: 'Start date must be before end date',
    path: ['start_time'],
  });

// Trading task validation schema
export const tradingTaskSchema = z.object({
  config_id: z.number().positive('Configuration is required'),
  account_id: z.number().positive('Account is required'),
  name: z
    .string()
    .min(1, 'Name is required')
    .max(255, 'Name must be less than 255 characters'),
  description: z.string().optional(),
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

// Instruments validation helper
export const validateInstruments = (
  instruments: string[],
  min: number = 1,
  max?: number
): { isValid: boolean; error?: string } => {
  if (instruments.length < min) {
    return {
      isValid: false,
      error: `At least ${min} instrument${min > 1 ? 's' : ''} required`,
    };
  }

  if (max !== undefined && instruments.length > max) {
    return {
      isValid: false,
      error: `Maximum ${max} instrument${max > 1 ? 's' : ''} allowed`,
    };
  }

  return { isValid: true };
};

// Export types inferred from schemas
export type ConfigurationFormData = z.infer<typeof configurationSchema>;
export type BacktestTaskFormData = z.infer<typeof backtestTaskSchema>;
export type TradingTaskFormData = z.infer<typeof tradingTaskSchema>;
export type CopyTaskFormData = z.infer<typeof copyTaskSchema>;
