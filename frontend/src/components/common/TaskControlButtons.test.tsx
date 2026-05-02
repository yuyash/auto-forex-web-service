import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { TaskStatus } from '../../types/common';
import { TaskControlButtons } from './TaskControlButtons';

describe('TaskControlButtons', () => {
  it('prevents duplicate clicks while an async action is pending', async () => {
    const user = userEvent.setup();
    const resolvers: Array<() => void> = [];
    const onStart = vi.fn(
      () =>
        new Promise<void>((resolve) => {
          resolvers.push(resolve);
        })
    );

    render(
      <TaskControlButtons
        taskId="task-1"
        status={TaskStatus.CREATED}
        onStart={onStart}
        showLabels
      />
    );

    const startButton = screen.getByRole('button', { name: /start/i });

    await user.click(startButton);
    fireEvent.click(startButton);

    expect(onStart).toHaveBeenCalledOnce();
    expect(onStart).toHaveBeenCalledWith('task-1');
    expect(startButton).toBeDisabled();

    await act(async () => {
      resolvers[0]();
    });

    await waitFor(() => expect(startButton).not.toBeDisabled());

    await user.click(startButton);

    expect(onStart).toHaveBeenCalledTimes(2);

    await act(async () => {
      resolvers[1]();
    });
  });

  it('does not call an action when the current status disables it', () => {
    const onStop = vi.fn();

    render(
      <TaskControlButtons
        taskId="task-1"
        status={TaskStatus.STOPPED}
        onStop={onStop}
        showLabels
      />
    );

    const stopButton = screen.getByRole('button', { name: /stop/i });

    expect(stopButton).toBeDisabled();

    fireEvent.click(stopButton);

    expect(onStop).not.toHaveBeenCalled();
  });
});
