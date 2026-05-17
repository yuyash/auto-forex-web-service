import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { InitialPositionSettingValue } from './InitialPositionSettingValue';

describe('InitialPositionSettingValue', () => {
  it('opens a dialog with execution-scoped initial position settings', () => {
    render(
      <InitialPositionSettingValue
        executionId="exec-123"
        value={[
          {
            direction: 'long',
            positions: [
              {
                layer_number: 1,
                retracement_count: 0,
                units: 1000,
                entry_price: '150.00',
                planned_exit_price: '150.50',
                stop_loss_price: '149.50',
                status: 'open',
              },
              {
                layer_number: 1,
                retracement_count: 1,
                status: 'closed_slot',
              },
            ],
          },
          {
            direction: 'short',
            positions: [
              {
                layer_number: 2,
                retracement_count: 0,
                units: 2000,
                entry_price: '151.00',
                exit_price: '150.20',
                close_reason: 'tp',
                status: 'closed',
                oanda_trade_id: 'OANDA-1',
              },
            ],
          },
        ]}
      />
    );

    expect(screen.getByText('2 cycles, 3 positions')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /view details/i }));

    expect(
      screen.getByRole('heading', { name: 'Initial position settings' })
    ).toBeInTheDocument();
    expect(screen.getByText('Execution ID: exec-123')).toBeInTheDocument();
    expect(screen.getByText('Cycle 1 - Long')).toBeInTheDocument();
    expect(screen.getByText('Cycle 2 - Short')).toBeInTheDocument();
    expect(screen.getByText('L1/R0')).toBeInTheDocument();
    expect(screen.getByText('L1/R1')).toBeInTheDocument();
    expect(screen.getByText('Closed slot')).toBeInTheDocument();
    expect(screen.getByText('OANDA-1')).toBeInTheDocument();
  });
});
