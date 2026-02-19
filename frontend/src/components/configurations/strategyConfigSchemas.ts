/**
 * Strategy configuration schemas and default parameters.
 *
 * Extracted from ConfigurationForm.tsx so the component file only exports
 * React components, which keeps react-refresh (Fast Refresh) working.
 */
import type { ConfigSchema } from '../../types/strategy';

const FLOOR_STRATEGY_SCHEMA: ConfigSchema = {
  type: 'object',
  title: 'Floor Strategy Configuration',
  description: 'Configuration for Floor strategy.',
  properties: {
    // ── Floor Parameters ─────────────────────────────────────────────
    lot_unit_size: {
      type: 'integer',
      title: 'Lot Unit Size',
      description:
        'How many currency units equal 1 lot (e.g. 1000 means 1 lot = 1,000 units).',
      default: 1000,
      minimum: 1,
      group: 'Floor Parameters',
    },
    base_lot_size: {
      type: 'number',
      title: 'Base Lot Size',
      description:
        'Lot size used for the very first entry in each layer. All subsequent lot calculations are based on this value.',
      default: 1.0,
      minimum: 0.01,
      group: 'Floor Parameters',
    },
    retracement_lot_mode: {
      type: 'string',
      title: 'Retracement Lot Mode',
      description:
        'How the lot size changes with each successive retracement entry within the same layer. Constant: same size every time, Additive: adds a fixed amount, Subtractive: subtracts a fixed amount (min 0.01), Multiplicative: doubles each time (base × 2^N), Divisive: halves each time (base / 2^N).',
      enum: [
        'constant',
        'additive',
        'subtractive',
        'multiplicative',
        'divisive',
      ],
      default: 'additive',
      group: 'Floor Parameters',
    },
    retracement_lot_amount: {
      type: 'number',
      title: 'Retracement Lot Amount',
      description:
        'The value used to adjust lot size per retracement. In Additive mode: lots = base + amount × N. In Subtractive mode: lots = base − amount × N (min 0.01).',
      default: 1.0,
      minimum: 0.01,
      dependsOn: {
        field: 'retracement_lot_mode',
        values: ['additive', 'subtractive'],
      },
      group: 'Floor Parameters',
    },
    retracement_pips: {
      type: 'number',
      title: 'Retracement Pips',
      description:
        'How many pips the price must move against you before a new retracement entry is opened. This is the base value for Layer 0.',
      default: 30,
      minimum: 1,
      group: 'Floor Parameters',
    },
    take_profit_pips_mode: {
      type: 'string',
      title: 'Take Profit Pips Mode',
      enum: [
        'constant',
        'additive',
        'subtractive',
        'multiplicative',
        'divisive',
      ],
      description:
        'How the take-profit target changes for each successive retracement entry within the same layer. Constant keeps the same TP for all entries.',
      default: 'constant',
      group: 'Floor Parameters',
    },
    take_profit_pips: {
      type: 'number',
      title: 'Take Profit Pips',
      description:
        'How many pips of profit are needed to close a position. This is the base value for the initial entry in Layer 0.',
      default: 25,
      minimum: 1,
      group: 'Floor Parameters',
    },
    take_profit_pips_amount: {
      type: 'number',
      title: 'Take Profit Pips Amount',
      description:
        'Pips added (or subtracted) per retracement entry. Example: base 25 + amount 3 → 1st retracement TP = 28, 2nd = 31.',
      default: 5.0,
      dependsOn: {
        field: 'take_profit_pips_mode',
        values: ['additive', 'subtractive'],
      },
      group: 'Floor Parameters',
    },

    // ── Layer Parameters ─────────────────────────────────────────────
    max_layers: {
      type: 'integer',
      title: 'Maximum Layers',
      description:
        'Maximum number of layers that can be open at the same time. When all retracements in a layer are exhausted, a new layer opens if this limit allows.',
      default: 3,
      minimum: 1,
      group: 'Layer Parameters',
    },
    max_retracements_per_layer: {
      type: 'integer',
      title: 'Max Retracements Per Layer',
      description:
        'Maximum number of additional retracement entries allowed in a single layer before the strategy moves to a new layer.',
      default: 10,
      minimum: 1,
      group: 'Layer Parameters',
    },
    retracement_trigger_progression: {
      type: 'string',
      title: 'Retracement Trigger Progression',
      enum: [
        'constant',
        'additive',
        'subtractive',
        'multiplicative',
        'divisive',
      ],
      description:
        'How the retracement trigger pips change when a new layer opens. Layer 0 always uses the base Retracement Pips value.',
      default: 'constant',
      group: 'Layer Parameters',
    },
    retracement_trigger_increment: {
      type: 'number',
      title: 'Retracement Trigger Increment',
      description:
        'Pips added (or subtracted) per layer. Example: base 30 + increment 5 → Layer 1 = 35, Layer 2 = 40.',
      default: 5.0,
      dependsOn: {
        field: 'retracement_trigger_progression',
        values: ['additive', 'subtractive'],
      },
      group: 'Layer Parameters',
    },
    take_profit_trigger_progression: {
      type: 'string',
      title: 'Take Profit Trigger Progression',
      enum: [
        'constant',
        'additive',
        'subtractive',
        'multiplicative',
        'divisive',
      ],
      description:
        'How the starting take-profit pips change when a new layer opens. Layer 0 always uses the base Take Profit Pips value.',
      default: 'constant',
      group: 'Layer Parameters',
    },
    take_profit_trigger_increment: {
      type: 'number',
      title: 'Take Profit Trigger Increment',
      description:
        'Pips added (or subtracted) per layer. Example: base 25 + increment 5 → Layer 1 = 30, Layer 2 = 35.',
      default: 5.0,
      dependsOn: {
        field: 'take_profit_trigger_progression',
        values: ['additive', 'subtractive'],
      },
      group: 'Layer Parameters',
    },

    // ── Margin Parameters ────────────────────────────────────────────
    margin_protection_enabled: {
      type: 'boolean',
      title: 'Margin Protection Enabled',
      default: true,
      description:
        'Automatically close positions when margin usage becomes dangerously high.',
      group: 'Margin Parameters',
    },
    margin_rate: {
      type: 'number',
      title: 'Margin Rate',
      default: 0.04,
      description:
        'Broker margin rate (e.g. 0.04 = 4% margin, equivalent to 25× leverage).',
      dependsOn: {
        field: 'margin_protection_enabled',
        values: ['true'],
      },
      group: 'Margin Parameters',
    },
    margin_cut_start_ratio: {
      type: 'number',
      title: 'Margin Cut Start Ratio',
      default: 0.6,
      description:
        'Start forced position reduction when margin ratio reaches this level (e.g. 0.6 = 60%).',
      dependsOn: {
        field: 'margin_protection_enabled',
        values: ['true'],
      },
      group: 'Margin Parameters',
    },
    margin_cut_target_ratio: {
      type: 'number',
      title: 'Margin Cut Target Ratio',
      default: 0.5,
      description:
        'Reduce positions until margin ratio drops to this level (e.g. 0.5 = 50%).',
      dependsOn: {
        field: 'margin_protection_enabled',
        values: ['true'],
      },
      group: 'Margin Parameters',
    },

    // ── Volatility Parameters ────────────────────────────────────────
    volatility_check_enabled: {
      type: 'boolean',
      title: 'Volatility Check Enabled',
      default: true,
      description:
        'Pause trading when market volatility (ATR) spikes above normal levels.',
      group: 'Volatility Parameters',
    },
    volatility_lock_multiplier: {
      type: 'number',
      title: 'Volatility Lock Multiplier',
      description:
        'Pause trading when current ATR exceeds baseline ATR by this multiplier (e.g. 5.0 = 5× normal volatility).',
      default: 5.0,
      minimum: 1,
      dependsOn: {
        field: 'volatility_check_enabled',
        values: ['true'],
      },
      group: 'Volatility Parameters',
    },
    volatility_unlock_multiplier: {
      type: 'number',
      title: 'Volatility Unlock Multiplier',
      default: 1.5,
      description:
        'Resume trading when current ATR drops below baseline ATR by this multiplier.',
      dependsOn: {
        field: 'volatility_check_enabled',
        values: ['true'],
      },
      group: 'Volatility Parameters',
    },
    atr_period: {
      type: 'integer',
      title: 'ATR Period',
      default: 14,
      description: 'Number of candles used to calculate the current ATR value.',
      dependsOn: {
        field: 'volatility_check_enabled',
        values: ['true'],
        or: [
          {
            field: 'dynamic_parameter_adjustment_enabled',
            values: ['true'],
          },
        ],
      },
      group: 'Volatility Parameters',
    },
    atr_baseline_period: {
      type: 'integer',
      title: 'ATR Baseline Period',
      default: 50,
      description:
        'Number of candles used to calculate the baseline ATR for comparison.',
      dependsOn: {
        field: 'volatility_check_enabled',
        values: ['true'],
        or: [
          {
            field: 'dynamic_parameter_adjustment_enabled',
            values: ['true'],
          },
        ],
      },
      group: 'Volatility Parameters',
    },

    // ── Direction Detection Parameters ───────────────────────────────
    entry_signal_lookback_candles: {
      type: 'integer',
      title: 'Candle Lookback Count',
      default: 50,
      description:
        'Number of candles analyzed to determine the initial entry direction (long or short).',
      minimum: 1,
      group: 'Direction Detection Parameters',
    },
    entry_signal_candle_granularity_seconds: {
      type: 'integer',
      title: 'Candle Granularity (seconds)',
      default: 60,
      description:
        'Duration of each candle in seconds. 60 = 1-minute candles, 300 = 5-minute candles.',
      minimum: 1,
      group: 'Direction Detection Parameters',
    },

    allow_duplicate_units: {
      type: 'boolean',
      title: 'Allow Duplicate Units',
      default: false,
      description:
        'When disabled, the system automatically adjusts position sizes to avoid having two entries with the exact same unit count in the same layer.',
      group: 'Floor Parameters',
    },
    hedging_enabled: {
      type: 'boolean',
      title: 'Hedging Enabled',
      default: false,
      description:
        'Allow holding both long and short positions at the same time. When disabled, positions are closed in FIFO order (US regulation).',
      group: 'Floor Parameters',
    },
    dynamic_parameter_adjustment_enabled: {
      type: 'boolean',
      title: 'Dynamic Parameter Adjustment',
      default: false,
      description:
        'Automatically widen or tighten retracement triggers and take-profit targets based on current volatility.',
      dependsOn: {
        field: 'volatility_check_enabled',
        values: ['true'],
      },
      group: 'Floor Parameters',
    },
    market_condition_override_enabled: {
      type: 'boolean',
      title: 'Spread Breaker',
      default: true,
      description:
        'Skip new entries when the bid-ask spread is abnormally wide.',
      group: 'Floor Parameters',
    },
    market_condition_spread_limit_pips: {
      type: 'number',
      title: 'Spread Limit (pips)',
      default: 3.0,
      description:
        'Do not open new entries when the spread exceeds this many pips.',
      dependsOn: {
        field: 'market_condition_override_enabled',
        values: ['true'],
      },
      group: 'Floor Parameters',
    },
  },
  required: [
    'base_lot_size',
    'retracement_lot_mode',
    'retracement_lot_amount',
    'retracement_pips',
    'take_profit_pips',
  ],
};

export const STRATEGY_CONFIG_SCHEMAS: Record<string, ConfigSchema> = {
  floor: FLOOR_STRATEGY_SCHEMA,
};
