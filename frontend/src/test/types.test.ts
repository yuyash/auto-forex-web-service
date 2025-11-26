import { describe, it, expect } from 'vitest';
import type {
  StrategyEvent,
  Trade,
  BacktestTask,
  TradingTask,
  BacktestTaskCreateData,
  BacktestTaskFormData,
  BacktestTaskUpdateData,
  TradingTaskCreateData,
  TradingTaskUpdateData,
} from '../types';
import { TaskStatus, DataSource } from '../types/common';

describe('Type Definitions', () => {
  describe('StrategyEvent', () => {
    it('accepts all valid event types', () => {
      const eventTypes: StrategyEvent['event_type'][] = [
        'initial',
        'retracement',
        'layer',
        'close',
        'take_profit',
        'volatility_lock',
        'margin_protection',
      ];

      eventTypes.forEach((eventType) => {
        const event: StrategyEvent = {
          event_type: eventType,
          timestamp: '2024-01-15T10:30:00Z',
          layer_number: 1,
          retracement_count: 0,
        };

        expect(event.event_type).toBe(eventType);
      });
    });

    it('includes required fields', () => {
      const event: StrategyEvent = {
        event_type: 'initial',
        timestamp: '2024-01-15T10:30:00Z',
        layer_number: 1,
        retracement_count: 0,
      };

      expect(event).toHaveProperty('event_type');
      expect(event).toHaveProperty('timestamp');
      expect(event).toHaveProperty('layer_number');
      expect(event).toHaveProperty('retracement_count');
    });

    it('includes optional fields for entry events', () => {
      const event: StrategyEvent = {
        event_type: 'initial',
        timestamp: '2024-01-15T10:30:00Z',
        layer_number: 1,
        retracement_count: 0,
        direction: 'long',
        units: 1000,
        entry_price: 149.5,
      };

      expect(event.direction).toBe('long');
      expect(event.units).toBe(1000);
      expect(event.entry_price).toBe(149.5);
    });

    it('includes optional fields for close events', () => {
      const event: StrategyEvent = {
        event_type: 'close',
        timestamp: '2024-01-15T11:45:00Z',
        layer_number: 1,
        retracement_count: 0,
        exit_price: 149.75,
        pnl: 250.0,
      };

      expect(event.exit_price).toBe(149.75);
      expect(event.pnl).toBe(250.0);
    });

    it('accepts metadata field', () => {
      const event: StrategyEvent = {
        event_type: 'take_profit',
        timestamp: '2024-01-15T12:00:00Z',
        layer_number: 1,
        retracement_count: 0,
        metadata: {
          reason: 'target_reached',
          target_price: 150.0,
        },
      };

      expect(event.metadata).toBeDefined();
      expect(event.metadata?.reason).toBe('target_reached');
    });
  });

  describe('Trade', () => {
    it('includes Floor Strategy fields', () => {
      const trade: Trade = {
        entry_time: '2024-01-15T10:30:00Z',
        exit_time: '2024-01-15T11:45:00Z',
        instrument: 'USD_JPY',
        direction: 'long',
        units: 1000,
        entry_price: 149.5,
        exit_price: 149.75,
        pnl: 250.0,
        layer_number: 1,
        is_first_lot: true,
        retracement_count: 0,
      };

      expect(trade).toHaveProperty('layer_number');
      expect(trade).toHaveProperty('is_first_lot');
      expect(trade).toHaveProperty('retracement_count');
      expect(trade.layer_number).toBe(1);
      expect(trade.is_first_lot).toBe(true);
      expect(trade.retracement_count).toBe(0);
    });

    it('allows optional Floor Strategy fields', () => {
      const trade: Trade = {
        entry_time: '2024-01-15T10:30:00Z',
        exit_time: '2024-01-15T11:45:00Z',
        instrument: 'USD_JPY',
        direction: 'long',
        units: 1000,
        entry_price: 149.5,
        exit_price: 149.75,
        pnl: 250.0,
      };

      expect(trade.layer_number).toBeUndefined();
      expect(trade.is_first_lot).toBeUndefined();
      expect(trade.retracement_count).toBeUndefined();
    });
  });

  describe('BacktestTask', () => {
    it('includes sell_at_completion field', () => {
      const task: BacktestTask = {
        id: 1,
        user_id: 1,
        config_id: 1,
        config_name: 'Test Config',
        strategy_type: 'FloorStrategy',
        name: 'Test Backtest',
        description: 'Test description',
        data_source: DataSource.OANDA,
        start_time: '2024-01-01T00:00:00Z',
        end_time: '2024-01-31T23:59:59Z',
        initial_balance: '10000.00',
        commission_per_trade: '0.00',
        instrument: 'USD_JPY',
        status: TaskStatus.PENDING,
        sell_at_completion: true,
        created_at: '2024-01-15T10:00:00Z',
        updated_at: '2024-01-15T10:00:00Z',
      };

      expect(task).toHaveProperty('sell_at_completion');
      expect(task.sell_at_completion).toBe(true);
    });

    it('allows sell_at_completion to be false', () => {
      const task: BacktestTask = {
        id: 1,
        user_id: 1,
        config_id: 1,
        config_name: 'Test Config',
        strategy_type: 'FloorStrategy',
        name: 'Test Backtest',
        description: 'Test description',
        data_source: DataSource.OANDA,
        start_time: '2024-01-01T00:00:00Z',
        end_time: '2024-01-31T23:59:59Z',
        initial_balance: '10000.00',
        commission_per_trade: '0.00',
        instrument: 'USD_JPY',
        status: TaskStatus.PENDING,
        sell_at_completion: false,
        created_at: '2024-01-15T10:00:00Z',
        updated_at: '2024-01-15T10:00:00Z',
      };

      expect(task.sell_at_completion).toBe(false);
    });
  });

  describe('BacktestTaskCreateData', () => {
    it('includes optional sell_at_completion field', () => {
      const createData: BacktestTaskCreateData = {
        config_id: 1,
        name: 'Test Backtest',
        description: 'Test description',
        data_source: DataSource.OANDA,
        start_time: '2024-01-01T00:00:00Z',
        end_time: '2024-01-31T23:59:59Z',
        initial_balance: 10000,
        commission_per_trade: 0,
        instrument: 'USD_JPY',
        sell_at_completion: true,
      };

      expect(createData).toHaveProperty('sell_at_completion');
      expect(createData.sell_at_completion).toBe(true);
    });

    it('allows sell_at_completion to be omitted', () => {
      const createData: BacktestTaskCreateData = {
        config_id: 1,
        name: 'Test Backtest',
        data_source: DataSource.OANDA,
        start_time: '2024-01-01T00:00:00Z',
        end_time: '2024-01-31T23:59:59Z',
        initial_balance: 10000,
        instrument: 'USD_JPY',
      };

      expect(createData.sell_at_completion).toBeUndefined();
    });
  });

  describe('BacktestTaskFormData', () => {
    it('includes optional sell_at_completion field', () => {
      const formData: BacktestTaskFormData = {
        config_id: 1,
        name: 'Test Backtest',
        data_source: DataSource.OANDA,
        start_time: '2024-01-01T00:00:00Z',
        end_time: '2024-01-31T23:59:59Z',
        initial_balance: 10000,
        instrument: 'USD_JPY',
        sell_at_completion: false,
      };

      expect(formData).toHaveProperty('sell_at_completion');
      expect(formData.sell_at_completion).toBe(false);
    });
  });

  describe('BacktestTaskUpdateData', () => {
    it('includes optional sell_at_completion field', () => {
      const updateData: BacktestTaskUpdateData = {
        name: 'Updated Name',
        sell_at_completion: true,
      };

      expect(updateData).toHaveProperty('sell_at_completion');
      expect(updateData.sell_at_completion).toBe(true);
    });

    it('allows updating only sell_at_completion', () => {
      const updateData: BacktestTaskUpdateData = {
        sell_at_completion: false,
      };

      expect(updateData.sell_at_completion).toBe(false);
      expect(updateData.name).toBeUndefined();
    });
  });

  describe('TradingTask', () => {
    it('includes sell_on_stop field', () => {
      const task: TradingTask = {
        id: 1,
        user_id: 1,
        config_id: 1,
        config_name: 'Test Config',
        strategy_type: 'FloorStrategy',
        account_id: 1,
        account_name: 'Test Account',
        account_type: 'practice',
        name: 'Test Trading Task',
        description: 'Test description',
        status: TaskStatus.PENDING,
        sell_on_stop: true,
        created_at: '2024-01-15T10:00:00Z',
        updated_at: '2024-01-15T10:00:00Z',
      };

      expect(task).toHaveProperty('sell_on_stop');
      expect(task.sell_on_stop).toBe(true);
    });

    it('allows sell_on_stop to be false', () => {
      const task: TradingTask = {
        id: 1,
        user_id: 1,
        config_id: 1,
        config_name: 'Test Config',
        strategy_type: 'FloorStrategy',
        account_id: 1,
        account_name: 'Test Account',
        account_type: 'practice',
        name: 'Test Trading Task',
        description: 'Test description',
        status: TaskStatus.PENDING,
        sell_on_stop: false,
        created_at: '2024-01-15T10:00:00Z',
        updated_at: '2024-01-15T10:00:00Z',
      };

      expect(task.sell_on_stop).toBe(false);
    });
  });

  describe('TradingTaskCreateData', () => {
    it('includes optional sell_on_stop field', () => {
      const createData: TradingTaskCreateData = {
        config_id: 1,
        account_id: 1,
        name: 'Test Trading Task',
        description: 'Test description',
        sell_on_stop: true,
      };

      expect(createData).toHaveProperty('sell_on_stop');
      expect(createData.sell_on_stop).toBe(true);
    });

    it('allows sell_on_stop to be omitted', () => {
      const createData: TradingTaskCreateData = {
        config_id: 1,
        account_id: 1,
        name: 'Test Trading Task',
      };

      expect(createData.sell_on_stop).toBeUndefined();
    });
  });

  describe('TradingTaskUpdateData', () => {
    it('includes optional sell_on_stop field', () => {
      const updateData: TradingTaskUpdateData = {
        name: 'Updated Name',
        sell_on_stop: true,
      };

      expect(updateData).toHaveProperty('sell_on_stop');
      expect(updateData.sell_on_stop).toBe(true);
    });

    it('allows updating only sell_on_stop', () => {
      const updateData: TradingTaskUpdateData = {
        sell_on_stop: false,
      };

      expect(updateData.sell_on_stop).toBe(false);
      expect(updateData.name).toBeUndefined();
    });
  });
});
