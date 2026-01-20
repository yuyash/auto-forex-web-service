/**
 * TaskControlButtons Unit Tests
 *
 * Tests for the TaskControlButtons component.
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { TaskControlButtons } from '../../../../src/components/common/TaskControlButtons';

describe('TaskControlButtons', () => {
  it('should render start button when status is idle', () => {
    const handleStart = vi.fn();
    render(
      <TaskControlButtons
        taskId={1}
        status="idle"
        onStart={handleStart}
        showLabels={true}
      />
    );

    const startButton = screen.getByRole('button', { name: /start/i });
    expect(startButton).toBeInTheDocument();
    expect(startButton).not.toBeDisabled();
  });

  it('should call onStart when start button is clicked', () => {
    const handleStart = vi.fn();
    render(
      <TaskControlButtons
        taskId={1}
        status="idle"
        onStart={handleStart}
        showLabels={true}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /start/i }));
    expect(handleStart).toHaveBeenCalledWith(1);
  });

  it('should enable stop button when status is running', () => {
    const handleStop = vi.fn();
    render(
      <TaskControlButtons
        taskId={1}
        status="running"
        onStop={handleStop}
        showLabels={true}
      />
    );

    const stopButton = screen.getByRole('button', { name: /stop/i });
    expect(stopButton).toBeInTheDocument();
    expect(stopButton).not.toBeDisabled();
  });

  it('should call onStop when stop button is clicked', () => {
    const handleStop = vi.fn();
    render(
      <TaskControlButtons
        taskId={1}
        status="running"
        onStop={handleStop}
        showLabels={true}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /stop/i }));
    expect(handleStop).toHaveBeenCalledWith(1);
  });

  it('should enable resume button when status is paused', () => {
    const handleResume = vi.fn();
    render(
      <TaskControlButtons
        taskId={1}
        status="paused"
        onResume={handleResume}
        showLabels={true}
      />
    );

    const resumeButton = screen.getByRole('button', { name: /resume/i });
    expect(resumeButton).toBeInTheDocument();
    expect(resumeButton).not.toBeDisabled();
  });

  it('should call onResume when resume button is clicked', () => {
    const handleResume = vi.fn();
    render(
      <TaskControlButtons
        taskId={1}
        status="paused"
        onResume={handleResume}
        showLabels={true}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /resume/i }));
    expect(handleResume).toHaveBeenCalledWith(1);
  });

  it('should enable restart button when status is stopped', () => {
    const handleRestart = vi.fn();
    render(
      <TaskControlButtons
        taskId={1}
        status="stopped"
        onRestart={handleRestart}
        showLabels={true}
      />
    );

    const restartButton = screen.getByRole('button', { name: /restart/i });
    expect(restartButton).toBeInTheDocument();
    expect(restartButton).not.toBeDisabled();
  });

  it('should call onRestart when restart button is clicked', () => {
    const handleRestart = vi.fn();
    render(
      <TaskControlButtons
        taskId={1}
        status="stopped"
        onRestart={handleRestart}
        showLabels={true}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /restart/i }));
    expect(handleRestart).toHaveBeenCalledWith(1);
  });

  it('should enable delete button when status is not running or paused', () => {
    const handleDelete = vi.fn();
    render(
      <TaskControlButtons
        taskId={1}
        status="stopped"
        onDelete={handleDelete}
        showLabels={true}
      />
    );

    const deleteButton = screen.getByRole('button', { name: /delete/i });
    expect(deleteButton).toBeInTheDocument();
    expect(deleteButton).not.toBeDisabled();
  });

  it('should call onDelete when delete button is clicked', () => {
    const handleDelete = vi.fn();
    render(
      <TaskControlButtons
        taskId={1}
        status="stopped"
        onDelete={handleDelete}
        showLabels={true}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /delete/i }));
    expect(handleDelete).toHaveBeenCalledWith(1);
  });

  it('should disable start button when status is running', () => {
    const handleStart = vi.fn();
    render(
      <TaskControlButtons
        taskId={1}
        status="running"
        onStart={handleStart}
        showLabels={true}
      />
    );

    const startButton = screen.getByRole('button', { name: /start/i });
    expect(startButton).toBeDisabled();
  });

  it('should disable delete button when status is running', () => {
    const handleDelete = vi.fn();
    render(
      <TaskControlButtons
        taskId={1}
        status="running"
        onDelete={handleDelete}
        showLabels={true}
      />
    );

    const deleteButton = screen.getByRole('button', { name: /delete/i });
    expect(deleteButton).toBeDisabled();
  });

  it('should show loading spinner when isLoading is true', () => {
    render(
      <TaskControlButtons
        taskId={1}
        status="idle"
        onStart={vi.fn()}
        isLoading={true}
      />
    );

    expect(screen.getByRole('progressbar')).toBeInTheDocument();
  });

  it('should disable all buttons when disabled prop is true', () => {
    render(
      <TaskControlButtons
        taskId={1}
        status="idle"
        onStart={vi.fn()}
        onStop={vi.fn()}
        onDelete={vi.fn()}
        disabled={true}
        showLabels={true}
      />
    );

    const buttons = screen.getAllByRole('button');
    buttons.forEach((button) => {
      expect(button).toBeDisabled();
    });
  });

  it('should render icon-only buttons when showLabels is false', () => {
    render(
      <TaskControlButtons
        taskId={1}
        status="idle"
        onStart={vi.fn()}
        showLabels={false}
      />
    );

    // Icon buttons should have aria-label but no visible text
    const startButtons = screen.getAllByLabelText('Start');
    expect(startButtons.length).toBeGreaterThan(0);
    expect(screen.queryByText('Start')).not.toBeInTheDocument();
  });

  it('should render buttons with labels when showLabels is true', () => {
    render(
      <TaskControlButtons
        taskId={1}
        status="idle"
        onStart={vi.fn()}
        showLabels={true}
      />
    );

    expect(screen.getByText('Start')).toBeInTheDocument();
  });

  it('should handle async callbacks', async () => {
    const handleStart = vi.fn().mockResolvedValue(undefined);
    render(
      <TaskControlButtons
        taskId={1}
        status="idle"
        onStart={handleStart}
        showLabels={true}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /start/i }));
    expect(handleStart).toHaveBeenCalledWith(1);
  });

  it('should not render buttons for callbacks that are not provided', () => {
    render(
      <TaskControlButtons
        taskId={1}
        status="idle"
        onStart={vi.fn()}
        showLabels={true}
      />
    );

    expect(screen.getByRole('button', { name: /start/i })).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /stop/i })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /pause/i })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /resume/i })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /restart/i })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /delete/i })
    ).not.toBeInTheDocument();
  });
});
