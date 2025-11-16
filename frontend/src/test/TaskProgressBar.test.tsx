import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { TaskProgressBar } from '../components/tasks/display/TaskProgressBar';
import { TaskStatus } from '../types/common';

describe('TaskProgressBar', () => {
  it('renders progress bar for running tasks', () => {
    render(<TaskProgressBar status={TaskStatus.RUNNING} progress={50} />);

    const progressBars = screen.getAllByRole('progressbar');
    expect(progressBars.length).toBeGreaterThan(0);
    expect(progressBars[0]).toHaveAttribute('aria-valuenow', '50');
  });

  it('does not render progress bar for created tasks', () => {
    render(<TaskProgressBar status={TaskStatus.CREATED} progress={0} />);

    const progressBar = screen.queryByRole('progressbar');
    expect(progressBar).not.toBeInTheDocument();
  });

  it('does not render progress bar for stopped tasks', () => {
    render(<TaskProgressBar status={TaskStatus.STOPPED} progress={30} />);

    const progressBar = screen.queryByRole('progressbar');
    expect(progressBar).not.toBeInTheDocument();
  });

  it('does not render progress bar for completed tasks', () => {
    render(<TaskProgressBar status={TaskStatus.COMPLETED} progress={100} />);

    const progressBar = screen.queryByRole('progressbar');
    expect(progressBar).not.toBeInTheDocument();
  });

  it('does not render progress bar for failed tasks', () => {
    render(<TaskProgressBar status={TaskStatus.FAILED} progress={75} />);

    const progressBar = screen.queryByRole('progressbar');
    expect(progressBar).not.toBeInTheDocument();
  });

  it('shows progress percentage when showPercentage is true', () => {
    render(
      <TaskProgressBar
        status={TaskStatus.RUNNING}
        progress={45}
        showPercentage={true}
      />
    );

    expect(screen.getByText('45%')).toBeInTheDocument();
  });

  it('hides progress percentage when showPercentage is false', () => {
    render(
      <TaskProgressBar
        status={TaskStatus.RUNNING}
        progress={45}
        showPercentage={false}
      />
    );

    expect(screen.queryByText('45%')).not.toBeInTheDocument();
  });

  it('clamps progress value to 0-100 range', () => {
    const { rerender } = render(
      <TaskProgressBar status={TaskStatus.RUNNING} progress={-10} />
    );

    let progressBars = screen.getAllByRole('progressbar');
    expect(progressBars[0]).toHaveAttribute('aria-valuenow', '0');

    rerender(<TaskProgressBar status={TaskStatus.RUNNING} progress={150} />);

    progressBars = screen.getAllByRole('progressbar');
    expect(progressBars[0]).toHaveAttribute('aria-valuenow', '100');
  });

  it('displays estimated time remaining when provided', () => {
    render(
      <TaskProgressBar
        status={TaskStatus.RUNNING}
        progress={60}
        estimatedTimeRemaining="2m 30s"
      />
    );

    expect(screen.getByText(/2m 30s remaining/i)).toBeInTheDocument();
  });

  it('updates progress when prop changes', () => {
    const { rerender } = render(
      <TaskProgressBar status={TaskStatus.RUNNING} progress={25} />
    );

    let progressBars = screen.getAllByRole('progressbar');
    expect(progressBars[0]).toHaveAttribute('aria-valuenow', '25');
    expect(screen.getByText('25%')).toBeInTheDocument();

    rerender(<TaskProgressBar status={TaskStatus.RUNNING} progress={75} />);

    progressBars = screen.getAllByRole('progressbar');
    expect(progressBars[0]).toHaveAttribute('aria-valuenow', '75');
    expect(screen.getByText('75%')).toBeInTheDocument();
  });

  it('renders with different sizes', () => {
    const { rerender } = render(
      <TaskProgressBar status={TaskStatus.RUNNING} progress={50} size="small" />
    );

    expect(screen.getAllByRole('progressbar').length).toBeGreaterThan(0);

    rerender(
      <TaskProgressBar
        status={TaskStatus.RUNNING}
        progress={50}
        size="medium"
      />
    );

    expect(screen.getAllByRole('progressbar').length).toBeGreaterThan(0);

    rerender(
      <TaskProgressBar status={TaskStatus.RUNNING} progress={50} size="large" />
    );

    expect(screen.getAllByRole('progressbar').length).toBeGreaterThan(0);
  });

  it('has proper ARIA attributes', () => {
    render(<TaskProgressBar status={TaskStatus.RUNNING} progress={33} />);

    const progressBars = screen.getAllByRole('progressbar');
    expect(progressBars[0]).toHaveAttribute('aria-valuenow', '33');
    expect(progressBars[0]).toHaveAttribute('aria-valuemin', '0');
    expect(progressBars[0]).toHaveAttribute('aria-valuemax', '100');
    expect(progressBars[0]).toHaveAttribute('aria-label');
  });
});
