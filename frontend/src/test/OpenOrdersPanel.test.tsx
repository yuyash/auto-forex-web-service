import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { I18nextProvider } from 'react-i18next';
import i18n from '../i18n/config';
import OpenOrdersPanel from '../components/dashboard/OpenOrdersPanel';
import type { Order } from '../types/chart';

const mockOrders: Order[] = [
  {
    order_id: 'ORD-001',
    instrument: 'EUR_USD',
    order_type: 'limit',
    direction: 'long',
    units: 10000,
    price: 1.085,
    status: 'pending',
    created_at: '2024-01-15T10:30:00Z',
  },
  {
    order_id: 'ORD-002',
    instrument: 'GBP_USD',
    order_type: 'stop',
    direction: 'short',
    units: 5000,
    price: 1.265,
    status: 'open',
    created_at: '2024-01-15T11:00:00Z',
  },
  {
    order_id: 'ORD-003',
    instrument: 'USD_JPY',
    order_type: 'market',
    direction: 'long',
    units: 20000,
    status: 'filled',
    created_at: '2024-01-15T11:30:00Z',
  },
];

describe('OpenOrdersPanel', () => {
  it('renders the panel with title and order count', () => {
    const mockCancelOrder = vi.fn();
    render(
      <I18nextProvider i18n={i18n}>
        <OpenOrdersPanel orders={mockOrders} onCancelOrder={mockCancelOrder} />
      </I18nextProvider>
    );

    expect(screen.getByText('Open Orders')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
  });

  it('displays all orders with correct data', () => {
    const mockCancelOrder = vi.fn();
    render(
      <I18nextProvider i18n={i18n}>
        <OpenOrdersPanel orders={mockOrders} onCancelOrder={mockCancelOrder} />
      </I18nextProvider>
    );

    expect(screen.getByText('ORD-001')).toBeInTheDocument();
    expect(screen.getByText('ORD-002')).toBeInTheDocument();
    expect(screen.getByText('ORD-003')).toBeInTheDocument();
    expect(screen.getByText('EUR_USD')).toBeInTheDocument();
    expect(screen.getByText('GBP_USD')).toBeInTheDocument();
    expect(screen.getByText('USD_JPY')).toBeInTheDocument();
  });

  it('displays order types correctly', () => {
    const mockCancelOrder = vi.fn();
    render(
      <I18nextProvider i18n={i18n}>
        <OpenOrdersPanel orders={mockOrders} onCancelOrder={mockCancelOrder} />
      </I18nextProvider>
    );

    expect(screen.getByText('Limit')).toBeInTheDocument();
    expect(screen.getByText('Stop')).toBeInTheDocument();
    expect(screen.getByText('Market')).toBeInTheDocument();
  });

  it('displays order prices correctly', () => {
    const mockCancelOrder = vi.fn();
    render(
      <I18nextProvider i18n={i18n}>
        <OpenOrdersPanel orders={mockOrders} onCancelOrder={mockCancelOrder} />
      </I18nextProvider>
    );

    expect(screen.getByText('1.08500')).toBeInTheDocument();
    expect(screen.getByText('1.26500')).toBeInTheDocument();
  });

  it('displays order units correctly', () => {
    const mockCancelOrder = vi.fn();
    render(
      <I18nextProvider i18n={i18n}>
        <OpenOrdersPanel orders={mockOrders} onCancelOrder={mockCancelOrder} />
      </I18nextProvider>
    );

    expect(screen.getByText('10,000')).toBeInTheDocument();
    expect(screen.getByText('5,000')).toBeInTheDocument();
    expect(screen.getByText('20,000')).toBeInTheDocument();
  });

  it('displays order status with correct chips', () => {
    const mockCancelOrder = vi.fn();
    render(
      <I18nextProvider i18n={i18n}>
        <OpenOrdersPanel orders={mockOrders} onCancelOrder={mockCancelOrder} />
      </I18nextProvider>
    );

    expect(screen.getByText('pending')).toBeInTheDocument();
    expect(screen.getByText('open')).toBeInTheDocument();
    expect(screen.getByText('filled')).toBeInTheDocument();
  });

  it('calls onCancelOrder when cancel button is clicked', () => {
    const mockCancelOrder = vi.fn();
    render(
      <I18nextProvider i18n={i18n}>
        <OpenOrdersPanel orders={mockOrders} onCancelOrder={mockCancelOrder} />
      </I18nextProvider>
    );

    const cancelButtons = screen.getAllByText('Cancel Order');
    fireEvent.click(cancelButtons[0]);

    expect(mockCancelOrder).toHaveBeenCalledWith('ORD-001');
    expect(mockCancelOrder).toHaveBeenCalledTimes(1);
  });

  it('toggles panel expansion when header is clicked', async () => {
    const mockCancelOrder = vi.fn();
    render(
      <I18nextProvider i18n={i18n}>
        <OpenOrdersPanel orders={mockOrders} onCancelOrder={mockCancelOrder} />
      </I18nextProvider>
    );

    const header = screen.getByText('Open Orders').closest('div');
    expect(screen.getByText('ORD-001')).toBeInTheDocument();

    if (header) {
      fireEvent.click(header);
    }

    // After collapse, orders should not be visible
    await waitFor(() => {
      expect(screen.queryByText('ORD-001')).not.toBeInTheDocument();
    });

    // Click again to expand
    if (header) {
      fireEvent.click(header);
    }

    await waitFor(() => {
      expect(screen.getByText('ORD-001')).toBeInTheDocument();
    });
  });

  it('displays empty state when no orders', () => {
    const mockCancelOrder = vi.fn();
    render(
      <I18nextProvider i18n={i18n}>
        <OpenOrdersPanel orders={[]} onCancelOrder={mockCancelOrder} />
      </I18nextProvider>
    );

    expect(screen.getByText('No open orders')).toBeInTheDocument();
    expect(screen.getByText('0')).toBeInTheDocument();
  });

  it('disables cancel buttons when loading', () => {
    const mockCancelOrder = vi.fn();
    render(
      <I18nextProvider i18n={i18n}>
        <OpenOrdersPanel
          orders={mockOrders}
          onCancelOrder={mockCancelOrder}
          loading={true}
        />
      </I18nextProvider>
    );

    const cancelButtons = screen.getAllByText('Cancel Order');
    cancelButtons.forEach((button) => {
      expect(button.closest('button')).toBeDisabled();
    });
  });

  it('renders expand/collapse icon correctly', () => {
    const mockCancelOrder = vi.fn();
    const { container } = render(
      <I18nextProvider i18n={i18n}>
        <OpenOrdersPanel orders={mockOrders} onCancelOrder={mockCancelOrder} />
      </I18nextProvider>
    );

    const iconButton = container.querySelector('[aria-label="toggle panel"]');
    expect(iconButton).toBeInTheDocument();
  });

  it('formats units with locale string', () => {
    const mockCancelOrder = vi.fn();
    const largeOrder: Order[] = [
      {
        order_id: 'ORD-004',
        instrument: 'EUR_USD',
        order_type: 'limit',
        direction: 'long',
        units: 1000000,
        price: 1.085,
        status: 'pending',
        created_at: '2024-01-15T10:30:00Z',
      },
    ];

    render(
      <I18nextProvider i18n={i18n}>
        <OpenOrdersPanel orders={largeOrder} onCancelOrder={mockCancelOrder} />
      </I18nextProvider>
    );

    expect(screen.getByText('1,000,000')).toBeInTheDocument();
  });

  it('handles orders without price (market orders)', () => {
    const mockCancelOrder = vi.fn();
    const marketOrder: Order[] = [
      {
        order_id: 'ORD-005',
        instrument: 'EUR_USD',
        order_type: 'market',
        direction: 'long',
        units: 10000,
        status: 'pending',
        created_at: '2024-01-15T10:30:00Z',
      },
    ];

    render(
      <I18nextProvider i18n={i18n}>
        <OpenOrdersPanel orders={marketOrder} onCancelOrder={mockCancelOrder} />
      </I18nextProvider>
    );

    expect(screen.getByText('-')).toBeInTheDocument();
  });
});
