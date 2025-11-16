import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { TaskActionButtons } from '../components/tasks/actions/TaskActionButtons';
import { TaskStatus } from '../types/common';

describe('TaskActionButtons', () => {
  it('shows Start button for created tasks', () => {
    const onStart = vi.fn();
    render(
      <TaskActionButtons
        status={TaskStatus.CREATED}
        onStart={onStart}
        onDelete={vi.fn()}
      />
    );

    expect(
      screen.getByRole('button', { name: /start task/i })
    ).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /stop task/i })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /rerun task/i })
    ).not.toBeInTheDocument();
  });

  it('shows Start button for stopped tasks', () => {
    const onStart = vi.fn();
    render(
      <TaskActionButtons
        status={TaskStatus.STOPPED}
        onStart={onStart}
        onDelete={vi.fn()}
      />
    );

    expect(
      screen.getByRole('button', { name: /start task/i })
    ).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /stop task/i })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /rerun task/i })
    ).not.toBeInTheDocument();
  });

  it('shows Stop button for running tasks', () => {
    const onStop = vi.fn();
    render(
      <TaskActionButtons
        status={TaskStatus.RUNNING}
        onStop={onStop}
        onDelete={vi.fn()}
      />
    );

    expect(
      screen.getByRole('button', { name: /stop task/i })
    ).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /start task/i })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /rerun task/i })
    ).not.toBeInTheDocument();
  });

  it('shows Rerun button for completed tasks', () => {
    const onRerun = vi.fn();
    render(
      <TaskActionButtons
        status={TaskStatus.COMPLETED}
        onRerun={onRerun}
        onDelete={vi.fn()}
      />
    );

    expect(
      screen.getByRole('button', { name: /rerun task/i })
    ).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /start task/i })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /stop task/i })
    ).not.toBeInTheDocument();
  });

  it('shows Rerun button for failed tasks', () => {
    const onRerun = vi.fn();
    render(
      <TaskActionButtons
        status={TaskStatus.FAILED}
        onRerun={onRerun}
        onDelete={vi.fn()}
      />
    );

    expect(
      screen.getByRole('button', { name: /rerun task/i })
    ).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /start task/i })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /stop task/i })
    ).not.toBeInTheDocument();
  });

  it('disables all buttons during state transitions', () => {
    const onStart = vi.fn();
    const onDelete = vi.fn();
    render(
      <TaskActionButtons
        status={TaskStatus.CREATED}
        onStart={onStart}
        onDelete={onDelete}
        loading={true}
      />
    );

    const startButton = screen.getByRole('button', { name: /start task/i });
    const deleteButton = screen.getByRole('button', { name: /delete task/i });

    expect(startButton).toBeDisabled();
    expect(deleteButton).toBeDisabled();
  });

  it('disables Delete button for running tasks', () => {
    render(
      <TaskActionButtons
        status={TaskStatus.RUNNING}
        onStop={vi.fn()}
        onDelete={vi.fn()}
      />
    );

    const deleteButton = screen.getByRole('button', { name: /delete task/i });
    expect(deleteButton).toBeDisabled();
  });

  it('enables Delete button for non-running tasks', () => {
    render(
      <TaskActionButtons
        status={TaskStatus.COMPLETED}
        onRerun={vi.fn()}
        onDelete={vi.fn()}
      />
    );

    const deleteButton = screen.getByRole('button', { name: /delete task/i });
    expect(deleteButton).not.toBeDisabled();
  });

  it('calls onStart when Start button is clicked', () => {
    const onStart = vi.fn();
    render(
      <TaskActionButtons
        status={TaskStatus.CREATED}
        onStart={onStart}
        onDelete={vi.fn()}
      />
    );

    const startButton = screen.getByRole('button', { name: /start task/i });
    fireEvent.click(startButton);

    expect(onStart).toHaveBeenCalledTimes(1);
  });

  it('calls onStop when Stop button is clicked', () => {
    const onStop = vi.fn();
    render(
      <TaskActionButtons
        status={TaskStatus.RUNNING}
        onStop={onStop}
        onDelete={vi.fn()}
      />
    );

    const stopButton = screen.getByRole('button', { name: /stop task/i });
    fireEvent.click(stopButton);

    expect(onStop).toHaveBeenCalledTimes(1);
  });

  it('calls onRerun when Rerun button is clicked', () => {
    const onRerun = vi.fn();
    render(
      <TaskActionButtons
        status={TaskStatus.COMPLETED}
        onRerun={onRerun}
        onDelete={vi.fn()}
      />
    );

    const rerunButton = screen.getByRole('button', { name: /rerun task/i });
    fireEvent.click(rerunButton);

    expect(onRerun).toHaveBeenCalledTimes(1);
  });

  it('calls onDelete when Delete button is clicked', () => {
    const onDelete = vi.fn();
    render(
      <TaskActionButtons
        status={TaskStatus.COMPLETED}
        onRerun={vi.fn()}
        onDelete={onDelete}
      />
    );

    const deleteButton = screen.getByRole('button', { name: /delete task/i });
    fireEvent.click(deleteButton);

    expect(onDelete).toHaveBeenCalledTimes(1);
  });

  it('shows tooltip for disabled Delete button on running tasks', () => {
    render(
      <TaskActionButtons
        status={TaskStatus.RUNNING}
        onStop={vi.fn()}
        onDelete={vi.fn()}
      />
    );

    const deleteButton = screen.getByRole('button', { name: /delete task/i });
    expect(deleteButton).toBeDisabled();
  });
});
