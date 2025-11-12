import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { I18nextProvider } from 'react-i18next';
import i18n from '../i18n/config';
import StrategyControls from '../components/strategy/StrategyControls';
import type { StrategyStatus } from '../types/strategy';

const mockInactiveStatus: StrategyStatus = {
  is_active: false,
  strategy_type: null,
  config: null,
  instrument: [],
  state: null,
  created_at: null,
  updated_at: null,
};

const mockActiveStatus: StrategyStatus = {
  is_active: true,
  strategy_type: 'floor',
  config: {
    base_lot_size: 1.0,
    scaling_mode: 'additive',
  },
  instrument: 'EUR_USD',
  state: {
    status: 'running',
    positions_count: 2,
    total_pnl: 150.5,
    last_tick_time: '2025-01-01T12:00:00Z',
  },
  created_at: '2025-01-01T10:00:00Z',
  updated_at: '2025-01-01T12:00:00Z',
};

const renderWithI18n = (component: React.ReactElement) => {
  return render(<I18nextProvider i18n={i18n}>{component}</I18nextProvider>);
};

describe('StrategyControls', () => {
  let mockOnStart: () => void | Promise<void>;
  let mockOnStop: () => void | Promise<void>;

  beforeEach(() => {
    mockOnStart = vi.fn();
    mockOnStop = vi.fn();
  });

  describe('Button Rendering', () => {
    it('renders start and stop buttons', () => {
      renderWithI18n(
        <StrategyControls
          strategyStatus={mockInactiveStatus}
          onStart={mockOnStart}
          onStop={mockOnStop}
        />
      );

      expect(
        screen.getByRole('button', { name: /start strategy/i })
      ).toBeInTheDocument();
      expect(
        screen.getByRole('button', { name: /stop strategy/i })
      ).toBeInTheDocument();
    });

    it('shows inactive status alert when strategy is not active', () => {
      renderWithI18n(
        <StrategyControls
          strategyStatus={mockInactiveStatus}
          onStart={mockOnStart}
          onStop={mockOnStop}
        />
      );

      expect(screen.getByText(/strategy is not active/i)).toBeInTheDocument();
    });

    it('shows active status alert when strategy is active', () => {
      renderWithI18n(
        <StrategyControls
          strategyStatus={mockActiveStatus}
          onStart={mockOnStart}
          onStop={mockOnStop}
        />
      );

      expect(
        screen.getByText(/strategy is currently active/i)
      ).toBeInTheDocument();
    });

    it('displays strategy type when active', () => {
      renderWithI18n(
        <StrategyControls
          strategyStatus={mockActiveStatus}
          onStart={mockOnStart}
          onStop={mockOnStop}
        />
      );

      expect(screen.getByText(/type: floor/i)).toBeInTheDocument();
    });
  });

  describe('Button States - Inactive Strategy', () => {
    it('enables start button when strategy is inactive', () => {
      renderWithI18n(
        <StrategyControls
          strategyStatus={mockInactiveStatus}
          onStart={mockOnStart}
          onStop={mockOnStop}
        />
      );

      const startButton = screen.getByRole('button', {
        name: /start strategy/i,
      });
      expect(startButton).not.toBeDisabled();
    });

    it('disables stop button when strategy is inactive', () => {
      renderWithI18n(
        <StrategyControls
          strategyStatus={mockInactiveStatus}
          onStart={mockOnStart}
          onStop={mockOnStop}
        />
      );

      const stopButton = screen.getByRole('button', { name: /stop strategy/i });
      expect(stopButton).toBeDisabled();
    });
  });

  describe('Button States - Active Strategy', () => {
    it('disables start button when strategy is active', () => {
      renderWithI18n(
        <StrategyControls
          strategyStatus={mockActiveStatus}
          onStart={mockOnStart}
          onStop={mockOnStop}
        />
      );

      const startButton = screen.getByRole('button', {
        name: /start strategy/i,
      });
      expect(startButton).toBeDisabled();
    });

    it('enables stop button when strategy is active', () => {
      renderWithI18n(
        <StrategyControls
          strategyStatus={mockActiveStatus}
          onStart={mockOnStart}
          onStop={mockOnStop}
        />
      );

      const stopButton = screen.getByRole('button', { name: /stop strategy/i });
      expect(stopButton).not.toBeDisabled();
    });
  });

  describe('Disabled Prop', () => {
    it('disables both buttons when disabled prop is true', () => {
      renderWithI18n(
        <StrategyControls
          strategyStatus={mockInactiveStatus}
          onStart={mockOnStart}
          onStop={mockOnStop}
          disabled={true}
        />
      );

      const startButton = screen.getByRole('button', {
        name: /start strategy/i,
      });
      const stopButton = screen.getByRole('button', { name: /stop strategy/i });

      expect(startButton).toBeDisabled();
      expect(stopButton).toBeDisabled();
    });
  });

  describe('Loading State', () => {
    it('disables both buttons when loading prop is true', () => {
      renderWithI18n(
        <StrategyControls
          strategyStatus={mockInactiveStatus}
          onStart={mockOnStart}
          onStop={mockOnStop}
          loading={true}
        />
      );

      const startButton = screen.getByRole('button', {
        name: /start strategy/i,
      });
      const stopButton = screen.getByRole('button', { name: /stop strategy/i });

      expect(startButton).toBeDisabled();
      expect(stopButton).toBeDisabled();
    });
  });

  describe('Permission Props', () => {
    it('disables start button when canStart is false', () => {
      renderWithI18n(
        <StrategyControls
          strategyStatus={mockInactiveStatus}
          onStart={mockOnStart}
          onStop={mockOnStop}
          canStart={false}
        />
      );

      const startButton = screen.getByRole('button', {
        name: /start strategy/i,
      });
      expect(startButton).toBeDisabled();
    });

    it('disables stop button when canStop is false', () => {
      renderWithI18n(
        <StrategyControls
          strategyStatus={mockActiveStatus}
          onStart={mockOnStart}
          onStop={mockOnStop}
          canStop={false}
        />
      );

      const stopButton = screen.getByRole('button', { name: /stop strategy/i });
      expect(stopButton).toBeDisabled();
    });
  });

  describe('Start Confirmation Dialog', () => {
    it('shows confirmation dialog when start button is clicked', () => {
      renderWithI18n(
        <StrategyControls
          strategyStatus={mockInactiveStatus}
          onStart={mockOnStart}
          onStop={mockOnStop}
        />
      );

      const startButton = screen.getByRole('button', {
        name: /start strategy/i,
      });
      fireEvent.click(startButton);

      expect(screen.getByRole('dialog')).toBeInTheDocument();
      expect(
        screen.getByText(/are you sure you want to start this strategy/i)
      ).toBeInTheDocument();
    });

    it('calls onStart when start is confirmed', async () => {
      renderWithI18n(
        <StrategyControls
          strategyStatus={mockInactiveStatus}
          onStart={mockOnStart}
          onStop={mockOnStop}
        />
      );

      const startButton = screen.getByRole('button', {
        name: /start strategy/i,
      });
      fireEvent.click(startButton);

      const confirmButton = screen.getByRole('button', { name: /^start$/i });
      fireEvent.click(confirmButton);

      await waitFor(() => {
        expect(mockOnStart).toHaveBeenCalledTimes(1);
      });
    });

    it('does not call onStart when start is cancelled', async () => {
      renderWithI18n(
        <StrategyControls
          strategyStatus={mockInactiveStatus}
          onStart={mockOnStart}
          onStop={mockOnStop}
        />
      );

      const startButton = screen.getByRole('button', {
        name: /start strategy/i,
      });
      fireEvent.click(startButton);

      const cancelButton = screen.getByRole('button', { name: /cancel/i });
      fireEvent.click(cancelButton);

      await waitFor(() => {
        expect(mockOnStart).not.toHaveBeenCalled();
      });
    });

    it('closes dialog after confirming start', async () => {
      renderWithI18n(
        <StrategyControls
          strategyStatus={mockInactiveStatus}
          onStart={mockOnStart}
          onStop={mockOnStop}
        />
      );

      const startButton = screen.getByRole('button', {
        name: /start strategy/i,
      });
      fireEvent.click(startButton);

      const confirmButton = screen.getByRole('button', { name: /^start$/i });
      fireEvent.click(confirmButton);

      await waitFor(() => {
        expect(
          screen.queryByText(/are you sure you want to start this strategy/i)
        ).not.toBeInTheDocument();
      });
    });
  });

  describe('Stop Confirmation Dialog', () => {
    it('shows confirmation dialog when stop button is clicked', () => {
      renderWithI18n(
        <StrategyControls
          strategyStatus={mockActiveStatus}
          onStart={mockOnStart}
          onStop={mockOnStop}
        />
      );

      const stopButton = screen.getByRole('button', { name: /stop strategy/i });
      fireEvent.click(stopButton);

      expect(screen.getByRole('dialog')).toBeInTheDocument();
      expect(
        screen.getByText(/are you sure you want to stop this strategy/i)
      ).toBeInTheDocument();
    });

    it('calls onStop when stop is confirmed', async () => {
      renderWithI18n(
        <StrategyControls
          strategyStatus={mockActiveStatus}
          onStart={mockOnStart}
          onStop={mockOnStop}
        />
      );

      const stopButton = screen.getByRole('button', { name: /stop strategy/i });
      fireEvent.click(stopButton);

      const confirmButton = screen.getByRole('button', { name: /^stop$/i });
      fireEvent.click(confirmButton);

      await waitFor(() => {
        expect(mockOnStop).toHaveBeenCalledTimes(1);
      });
    });

    it('does not call onStop when stop is cancelled', async () => {
      renderWithI18n(
        <StrategyControls
          strategyStatus={mockActiveStatus}
          onStart={mockOnStart}
          onStop={mockOnStop}
        />
      );

      const stopButton = screen.getByRole('button', { name: /stop strategy/i });
      fireEvent.click(stopButton);

      const cancelButton = screen.getByRole('button', { name: /cancel/i });
      fireEvent.click(cancelButton);

      await waitFor(() => {
        expect(mockOnStop).not.toHaveBeenCalled();
      });
    });

    it('closes dialog after confirming stop', async () => {
      renderWithI18n(
        <StrategyControls
          strategyStatus={mockActiveStatus}
          onStart={mockOnStart}
          onStop={mockOnStop}
        />
      );

      const stopButton = screen.getByRole('button', { name: /stop strategy/i });
      fireEvent.click(stopButton);

      const confirmButton = screen.getByRole('button', { name: /^stop$/i });
      fireEvent.click(confirmButton);

      await waitFor(() => {
        expect(
          screen.queryByText(/are you sure you want to stop this strategy/i)
        ).not.toBeInTheDocument();
      });
    });
  });

  describe('Async Operations', () => {
    it('handles async onStart function', async () => {
      const asyncOnStart = vi.fn(async () => {
        await new Promise((resolve) => setTimeout(resolve, 100));
      });

      renderWithI18n(
        <StrategyControls
          strategyStatus={mockInactiveStatus}
          onStart={asyncOnStart}
          onStop={mockOnStop}
        />
      );

      const startButton = screen.getByRole('button', {
        name: /start strategy/i,
      });
      fireEvent.click(startButton);

      const confirmButton = screen.getByRole('button', { name: /^start$/i });
      fireEvent.click(confirmButton);

      await waitFor(() => {
        expect(asyncOnStart).toHaveBeenCalledTimes(1);
      });
    });

    it('handles async onStop function', async () => {
      const asyncOnStop = vi.fn(async () => {
        await new Promise((resolve) => setTimeout(resolve, 100));
      });

      renderWithI18n(
        <StrategyControls
          strategyStatus={mockActiveStatus}
          onStart={mockOnStart}
          onStop={asyncOnStop}
        />
      );

      const stopButton = screen.getByRole('button', { name: /stop strategy/i });
      fireEvent.click(stopButton);

      const confirmButton = screen.getByRole('button', { name: /^stop$/i });
      fireEvent.click(confirmButton);

      await waitFor(() => {
        expect(asyncOnStop).toHaveBeenCalledTimes(1);
      });
    });
  });

  describe('Null Strategy Status', () => {
    it('handles null strategy status gracefully', () => {
      renderWithI18n(
        <StrategyControls
          strategyStatus={null}
          onStart={mockOnStart}
          onStop={mockOnStop}
        />
      );

      const startButton = screen.getByRole('button', {
        name: /start strategy/i,
      });
      const stopButton = screen.getByRole('button', { name: /stop strategy/i });

      expect(startButton).toBeInTheDocument();
      expect(stopButton).toBeInTheDocument();
    });

    it('enables start button when strategy status is null', () => {
      renderWithI18n(
        <StrategyControls
          strategyStatus={null}
          onStart={mockOnStart}
          onStop={mockOnStop}
        />
      );

      const startButton = screen.getByRole('button', {
        name: /start strategy/i,
      });
      expect(startButton).not.toBeDisabled();
    });

    it('disables stop button when strategy status is null', () => {
      renderWithI18n(
        <StrategyControls
          strategyStatus={null}
          onStart={mockOnStart}
          onStop={mockOnStop}
        />
      );

      const stopButton = screen.getByRole('button', { name: /stop strategy/i });
      expect(stopButton).toBeDisabled();
    });
  });
});
