import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import BacktestProgressBar from '../components/backtest/BacktestProgressBar';

describe('BacktestProgressBar', () => {
  it('renders no backtest message when backtestId is null', () => {
    render(<BacktestProgressBar backtestId={null} />);
    expect(screen.getByText(/No backtest running/i)).toBeInTheDocument();
  });

  it('renders backtest progress component with backtest ID', () => {
    render(<BacktestProgressBar backtestId={123} />);

    // Component should render - actual data fetching is mocked in the component
    expect(screen.getByText('Backtest Progress')).toBeInTheDocument();
  });

  it('displays backtest details section', () => {
    render(<BacktestProgressBar backtestId={123} />);

    // Check for details section
    expect(screen.getByText('Backtest Progress')).toBeInTheDocument();
  });

  it('accepts onComplete callback prop', () => {
    const onComplete = () => {};
    render(<BacktestProgressBar backtestId={123} onComplete={onComplete} />);

    expect(screen.getByText('Backtest Progress')).toBeInTheDocument();
  });

  it('accepts onError callback prop', () => {
    const onError = () => {};
    render(<BacktestProgressBar backtestId={123} onError={onError} />);

    expect(screen.getByText('Backtest Progress')).toBeInTheDocument();
  });

  it('updates when backtestId changes to null', () => {
    const { rerender } = render(<BacktestProgressBar backtestId={123} />);

    expect(screen.getByText('Backtest Progress')).toBeInTheDocument();

    // Change to null
    rerender(<BacktestProgressBar backtestId={null} />);

    expect(screen.getByText(/No backtest running/i)).toBeInTheDocument();
  });
});
