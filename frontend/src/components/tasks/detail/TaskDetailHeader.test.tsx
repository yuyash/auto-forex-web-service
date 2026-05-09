import { act, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import i18n from '../../../i18n/config';
import { TaskStatus } from '../../../types/common';
import { TaskDetailHeader } from './TaskDetailHeader';

const noop = async () => {};

const baseProps = {
  taskId: 'task-1',
  taskName: 'Idle task',
  taskDescription: '',
  taskStatus: TaskStatus.IDLE,
  currentStatus: TaskStatus.IDLE,
  taskType: 'trading' as const,
  strategyName: 'Snowball',
  instrument: 'USD_JPY',
  tick: {
    timestamp: null,
    bid: null,
    ask: null,
    mid: null,
  },
  timezone: 'UTC',
  isMobile: false,
  progress: 0,
  completedLabel: 'completed',
  editLabel: 'Edit',
  deleteLabel: 'Delete',
  onStart: noop,
  onStop: noop,
  onRestart: noop,
  onResume: noop,
  onPause: noop,
  onEdit: noop,
  onDelete: noop,
};

describe('TaskDetailHeader', () => {
  afterEach(async () => {
    await act(async () => {
      await i18n.changeLanguage('en');
    });
  });

  it('shows the market-closed idle message in Japanese', async () => {
    await act(async () => {
      await i18n.changeLanguage('ja');
    });

    render(<TaskDetailHeader {...baseProps} />);

    expect(
      screen.getByText(
        'マーケットクローズ中のためタスクはアイドル状態です。マーケット再開後にトレーディングを再開します。'
      )
    ).toBeInTheDocument();
  });
});
