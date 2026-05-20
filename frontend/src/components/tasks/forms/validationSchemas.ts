import { z } from 'zod';
import { DataSource } from '../../../types/common';
import {
  currencyCodeSchema,
  optionalCurrencyCodeSchema,
} from './currencyValidation';

// Data source values array for Zod validation
const dataSourceValues = [
  DataSource.POSTGRESQL,
  DataSource.ATHENA,
  DataSource.S3,
] as const;

const requiredPositiveIntegerInputSchema = z
  .union([z.number(), z.string()])
  .refine(
    (value) => Number.isInteger(Number(value)) && Number(value) > 0,
    'Must be a positive integer'
  );
const nonNegativeIntegerInputSchema = z
  .union([z.number(), z.string()])
  .refine(
    (value) => Number.isInteger(Number(value)) && Number(value) >= 0,
    'Must be a non-negative integer'
  );
const optionalPositiveNumberSchema = z
  .union([z.number(), z.string(), z.null()])
  .optional()
  .refine(
    (value) =>
      value === undefined ||
      value === null ||
      value === '' ||
      (Number.isFinite(Number(value)) && Number(value) > 0),
    'Must be a positive number'
  );
const optionalPositiveIntegerInputSchema = z
  .union([z.number(), z.string(), z.null()])
  .optional()
  .refine(
    (value) =>
      value === undefined ||
      value === null ||
      value === '' ||
      (Number.isInteger(Number(value)) && Number(value) > 0),
    'Must be a positive integer'
  );
const excludedDateSchema = z
  .string()
  .regex(
    /^(\d{4}-\d{2}-\d{2}|\d{2}-\d{2})$/,
    'Each excluded date must be YYYY-MM-DD or MM-DD'
  );

const initialPositionSchema = z
  .object({
    layer_number: requiredPositiveIntegerInputSchema,
    retracement_count: nonNegativeIntegerInputSchema,
    units: optionalPositiveIntegerInputSchema,
    entry_price: optionalPositiveNumberSchema,
    planned_exit_price: optionalPositiveNumberSchema,
    stop_loss_price: optionalPositiveNumberSchema,
    status: z
      .enum(['open', 'closed', 'closed_slot', 'pending_rebuild'])
      .optional()
      .default('open'),
    exit_price: optionalPositiveNumberSchema,
    close_reason: z.string().optional(),
    oanda_trade_id: z.string().optional(),
  })
  .superRefine((position, ctx) => {
    if (position.status === 'closed_slot') {
      for (const field of [
        'units',
        'entry_price',
        'planned_exit_price',
        'stop_loss_price',
        'exit_price',
        'close_reason',
        'oanda_trade_id',
      ] as const) {
        if (hasInitialPositionInput(position[field])) {
          ctx.addIssue({
            code: 'custom',
            path: [field],
            message: 'Closed slot placeholders cannot define position values',
          });
        }
      }
      return;
    }

    if (!hasInitialPositionInput(position.units)) {
      ctx.addIssue({
        code: 'custom',
        path: ['units'],
        message: 'Must be a positive integer',
      });
    }
    if (!hasInitialPositionInput(position.entry_price)) {
      ctx.addIssue({
        code: 'custom',
        path: ['entry_price'],
        message: 'Must be a positive number',
      });
    }
  });

const initialPositionCycleSchema = z.object({
  direction: z.enum(['long', 'short']),
  positions: z.array(initialPositionSchema).min(1),
});

interface InitialPositionSlotLike {
  layer_number: unknown;
  retracement_count: unknown;
}

interface InitialPositionCycleLike {
  positions?: InitialPositionSlotLike[];
}

export function addInitialPositionSlotStructureIssues(
  cycles: InitialPositionCycleLike[],
  ctx: z.RefinementCtx
) {
  cycles.forEach((cycle, cycleIndex) => {
    const positions = Array.isArray(cycle.positions) ? cycle.positions : [];
    const seen = new Map<string, number>();
    const validPositions: Array<{
      positionIndex: number;
      layer: number;
      retracement: number;
    }> = [];

    positions.forEach((position, positionIndex) => {
      const layer = integerValue(position.layer_number);
      const retracement = integerValue(position.retracement_count);
      if (layer === null || retracement === null) {
        return;
      }

      const key = `${layer}:${retracement}`;
      if (seen.has(key)) {
        ctx.addIssue({
          code: 'custom',
          path: [
            'initial_position_cycles',
            cycleIndex,
            'positions',
            positionIndex,
            'retracement_count',
          ],
          message: `Duplicate L${layer}/R${retracement}`,
        });
        return;
      }
      seen.set(key, positionIndex);

      if (layer >= 1 && retracement >= 0) {
        validPositions.push({ positionIndex, layer, retracement });
      }
    });

    const byLayer = new Map<number, typeof validPositions>();
    validPositions.forEach((position) => {
      byLayer.set(position.layer, [
        ...(byLayer.get(position.layer) ?? []),
        position,
      ]);
    });

    for (const [layer, layerPositions] of [...byLayer.entries()].sort(
      ([left], [right]) => left - right
    )) {
      const byRetracement = new Map<number, (typeof validPositions)[number]>();
      layerPositions.forEach((position) => {
        byRetracement.set(position.retracement, position);
      });
      if (!byRetracement.has(0)) {
        const offender = [...layerPositions].sort(
          (left, right) => left.retracement - right.retracement
        )[0];
        ctx.addIssue({
          code: 'custom',
          path: [
            'initial_position_cycles',
            cycleIndex,
            'positions',
            offender.positionIndex,
            'retracement_count',
          ],
          message: `Layer L${layer} must start at R0.`,
        });
        continue;
      }
    }
  });
}

function integerValue(value: unknown): number | null {
  if (value === null || value === undefined || value === '') {
    return null;
  }
  const parsed = Number(value);
  return Number.isInteger(parsed) ? parsed : null;
}

function hasInitialPositionInput(value: unknown): boolean {
  return value !== undefined && value !== null && value !== '';
}

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
    config_id: z
      .string()
      .min(1, 'Configuration is required')
      .uuid('Configuration must be a valid ID'),
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
    account_currency: currencyCodeSchema,
    display_currency: optionalCurrencyCodeSchema,
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
    tick_granularity: z.enum([
      'tick',
      '1s',
      '10s',
      '15s',
      '30s',
      '1m',
      '5m',
      '15m',
      '30m',
      '1h',
    ]),
    tick_window_value_mode: z.enum(['first', 'last', 'average', 'median']),
    sell_at_completion: z.boolean().optional().default(false),
    hedging_enabled: z.boolean().optional().default(true),
    drain_duration_hours: z.coerce
      .number({ message: 'Drain duration must be a number' })
      .int('Drain duration must be an integer')
      .min(0, 'Drain duration cannot be negative')
      .optional(),
    market_idle_pre_close_minutes: z.coerce
      .number({ message: 'Must be a non-negative integer' })
      .int('Must be an integer')
      .min(0, 'Must be non-negative')
      .max(720, 'Must not exceed 720 minutes (12 hours)')
      .optional(),
    market_idle_resume_delay_minutes: z.coerce
      .number({ message: 'Must be a non-negative integer' })
      .int('Must be an integer')
      .min(0, 'Must be non-negative')
      .max(720, 'Must not exceed 720 minutes (12 hours)')
      .optional(),
    market_close_enabled: z.boolean().optional().default(false),
    market_close_weekday: z.coerce
      .number({ message: 'Weekday must be a number' })
      .int('Weekday must be an integer')
      .min(0, 'Weekday must be between 0 (Monday) and 6 (Sunday)')
      .max(6, 'Weekday must be between 0 (Monday) and 6 (Sunday)')
      .optional(),
    market_close_hour_utc: z.coerce
      .number({ message: 'Hour must be a number' })
      .int('Hour must be an integer')
      .min(0, 'Hour must be between 0 and 23')
      .max(23, 'Hour must be between 0 and 23')
      .optional(),
    market_open_weekday: z.coerce
      .number({ message: 'Weekday must be a number' })
      .int('Weekday must be an integer')
      .min(0, 'Weekday must be between 0 (Monday) and 6 (Sunday)')
      .max(6, 'Weekday must be between 0 (Monday) and 6 (Sunday)')
      .optional(),
    market_open_hour_utc: z.coerce
      .number({ message: 'Hour must be a number' })
      .int('Hour must be an integer')
      .min(0, 'Hour must be between 0 and 23')
      .max(23, 'Hour must be between 0 and 23')
      .optional(),
    max_tick_gap_hours: z.coerce
      .number({ message: 'Tick gap threshold must be a number' })
      .int('Tick gap threshold must be an integer')
      .min(1, 'Tick gap threshold must be at least 1 hour')
      .optional(),
    holidays_enabled: z.boolean().optional().default(false),
    excluded_dates: z.array(excludedDateSchema).optional().default([]),
    initial_positions_enabled: z.boolean().optional().default(false),
    initial_position_cycles: z
      .array(initialPositionCycleSchema)
      .optional()
      .default([]),
  })
  .superRefine((data, ctx) => {
    if (!data.initial_positions_enabled) {
      return;
    }
    if (!data.initial_position_cycles.length) {
      ctx.addIssue({
        code: 'custom',
        path: ['initial_position_cycles'],
        message: 'At least one initial cycle is required',
      });
    }
    addInitialPositionSlotStructureIssues(data.initial_position_cycles, ctx);
  })
  .refine((data) => data.start_time < data.end_time, {
    message: 'Start date must be before end date',
    path: ['start_time'],
  });

// Trading task validation schema
export const tradingTaskSchema = z.object({
  config_id: z.string().min(1, 'Configuration is required'),
  oanda_account_id: z.string().min(1, 'Account is required'),
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
// Explicitly define the output type
export type BacktestTaskSchemaOutput = {
  config_id: string;
  name: string;
  description?: string;
  data_source: DataSource;
  start_time: string;
  end_time: string;
  initial_balance: number;
  account_currency: string;
  display_currency?: string;
  commission_per_trade?: number;
  pip_size?: number;
  instrument: string;
  tick_granularity: string;
  tick_window_value_mode: string;
  sell_at_completion?: boolean;
  hedging_enabled?: boolean;
  drain_duration_hours?: number;
  market_idle_pre_close_minutes?: number;
  market_idle_resume_delay_minutes?: number;
  market_close_enabled?: boolean;
  market_close_weekday?: number;
  market_close_hour_utc?: number;
  market_open_weekday?: number;
  market_open_hour_utc?: number;
  max_tick_gap_hours?: number;
  holidays_enabled?: boolean;
  excluded_dates?: string[];
  initial_positions_enabled?: boolean;
  initial_position_cycles?: z.infer<typeof initialPositionCycleSchema>[];
};
export type TradingTaskFormData = z.infer<typeof tradingTaskSchema>;
export type CopyTaskFormData = z.infer<typeof copyTaskSchema>;
