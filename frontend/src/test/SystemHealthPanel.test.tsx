import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import SystemHealthPanel from '../components/admin/SystemHealthPanel';
import type { SystemHealth } from '../types/admin';

const mockHealthData: SystemHealth = {
  cpu_usage: 45.5,
  memory_usage: 62.3,
  database_status: 'connected',
  redis_status: 'connected',
  oanda_api_status: 'connected',
  active_streams: 5,
  celery_tasks: 12,
  timestamp: '2025-01-15T10:30:00Z',
};

const mockHealthDataDisconnected: SystemHealth = {
  cpu_usage: 85.2,
  memory_usage: 92.7,
  database_status: 'disconnected',
  redis_status: 'disconnected',
  oanda_api_status: 'disconnected',
  active_streams: 0,
  celery_tasks: 0,
  timestamp: '2025-01-15T10:30:00Z',
};

describe('SystemHealthPanel', () => {
  it('renders system health metrics', () => {
    render(<SystemHealthPanel health={mockHealthData} />);

    expect(screen.getByText('System Health')).toBeInTheDocument();
    expect(screen.getByText('45.5%')).toBeInTheDocument();
    expect(screen.getByText('62.3%')).toBeInTheDocument();
    expect(screen.getByText('5')).toBeInTheDocument();
    expect(screen.getByText('12')).toBeInTheDocument();
  });

  it('displays connection status indicators', () => {
    render(<SystemHealthPanel health={mockHealthData} />);

    expect(screen.getByText('Database')).toBeInTheDocument();
    expect(screen.getByText('Redis')).toBeInTheDocument();
    expect(screen.getByText('OANDA API')).toBeInTheDocument();
  });

  it('shows disconnected status correctly', () => {
    render(<SystemHealthPanel health={mockHealthDataDisconnected} />);

    expect(screen.getByText('85.2%')).toBeInTheDocument();
    expect(screen.getByText('92.7%')).toBeInTheDocument();
    expect(screen.getAllByText('0')).toHaveLength(2); // active_streams and celery_tasks
  });

  it('displays timestamp', () => {
    render(<SystemHealthPanel health={mockHealthData} />);

    expect(screen.getByText(/Last update:/)).toBeInTheDocument();
  });
});
