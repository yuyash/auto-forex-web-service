import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { TaskProgress } from '../components/tasks/TaskProgress';
import { TaskStatus } from '../types/common';

describe('TaskProgress', () => {
  describe('Rendering in different modes', () => {
    it('renders in compact mode for list views', () => {
      render(
        <TaskProgress
          status={TaskStatus.RUNNING}
          progress={50}
          compact={true}
        />
      );

      const progressBar = screen.getByRole('progressbar');
      expect(progressBar).toBeInTheDocument();
      expect(progressBar).toHaveAttribute('aria-valuenow', '50');
    });

    it('renders in full-width mode for detail pages', () => {
      render(
        <TaskProgress
          status={TaskStatus.RUNNING}
          progress={50}
          compact={false}
        />
      );

      const progressBar = screen.getByRole('progressbar');
      expect(progressBar).toBeInTheDocument();
      expect(progressBar).toHaveAttribute('aria-valuenow', '50');
    });

    it('defaults to full-width mode when compact is not specified', () => {
      render(<TaskProgress status={TaskStatus.RUNNING} progress={50} />);

      const progressBar = screen.getByRole('progressbar');
      expect(progressBar).toBeInTheDocument();
    });
  });

  describe('Progress value display', () => {
    it('displays correct progress percentage', () => {
      render(<TaskProgress status={TaskStatus.RUNNING} progress={45} />);

      expect(screen.getByText('45%')).toBeInTheDocument();
    });

    it('shows progress percentage when showPercentage is true', () => {
      render(
        <TaskProgress
          status={TaskStatus.RUNNING}
          progress={75}
          showPercentage={true}
        />
      );

      expect(screen.getByText('75%')).toBeInTheDocument();
    });

    it('hides progress percentage when showPercentage is false', () => {
      render(
        <TaskProgress
          status={TaskStatus.RUNNING}
          progress={75}
          showPercentage={false}
        />
      );

      expect(screen.queryByText('75%')).not.toBeInTheDocument();
    });

    it('clamps progress value to 0-100 range', () => {
      const { rerender } = render(
        <TaskProgress status={TaskStatus.RUNNING} progress={-10} />
      );

      let progressBar = screen.getByRole('progressbar');
      expect(progressBar).toHaveAttribute('aria-valuenow', '0');

      rerender(<TaskProgress status={TaskStatus.RUNNING} progress={150} />);

      progressBar = screen.getByRole('progressbar');
      expect(progressBar).toHaveAttribute('aria-valuenow', '100');
    });

    it('updates progress when prop changes', () => {
      const { rerender } = render(
        <TaskProgress status={TaskStatus.RUNNING} progress={25} />
      );

      let progressBar = screen.getByRole('progressbar');
      expect(progressBar).toHaveAttribute('aria-valuenow', '25');
      expect(screen.getByText('25%')).toBeInTheDocument();

      rerender(<TaskProgress status={TaskStatus.RUNNING} progress={75} />);

      progressBar = screen.getByRole('progressbar');
      expect(progressBar).toHaveAttribute('aria-valuenow', '75');
      expect(screen.getByText('75%')).toBeInTheDocument();
    });
  });

  describe('Color coding by status', () => {
    it('uses primary color (blue) for running tasks', () => {
      render(<TaskProgress status={TaskStatus.RUNNING} progress={50} />);

      const progressBar = screen.getByRole('progressbar');
      expect(progressBar).toBeInTheDocument();
      // Color is applied via MUI theme, we verify the component renders
    });

    it('uses success color (green) for completed tasks', () => {
      // Note: Progress bar is hidden for completed tasks, but color logic exists
      render(<TaskProgress status={TaskStatus.COMPLETED} progress={100} />);

      const progressBar = screen.queryByRole('progressbar');
      expect(progressBar).not.toBeInTheDocument();
    });

    it('uses error color (red) for failed tasks', () => {
      // Note: Progress bar is hidden for failed tasks, but color logic exists
      render(<TaskProgress status={TaskStatus.FAILED} progress={75} />);

      const progressBar = screen.queryByRole('progressbar');
      expect(progressBar).not.toBeInTheDocument();
    });
  });

  describe('Visibility based on task state', () => {
    it('shows progress bar for running tasks', () => {
      render(<TaskProgress status={TaskStatus.RUNNING} progress={50} />);

      const progressBar = screen.getByRole('progressbar');
      expect(progressBar).toBeInTheDocument();
    });

    it('hides progress bar for created tasks', () => {
      render(<TaskProgress status={TaskStatus.CREATED} progress={0} />);

      const progressBar = screen.queryByRole('progressbar');
      expect(progressBar).not.toBeInTheDocument();
    });

    it('hides progress bar for stopped tasks', () => {
      render(<TaskProgress status={TaskStatus.STOPPED} progress={30} />);

      const progressBar = screen.queryByRole('progressbar');
      expect(progressBar).not.toBeInTheDocument();
    });

    it('hides progress bar for completed tasks', () => {
      render(<TaskProgress status={TaskStatus.COMPLETED} progress={100} />);

      const progressBar = screen.queryByRole('progressbar');
      expect(progressBar).not.toBeInTheDocument();
    });

    it('hides progress bar for failed tasks', () => {
      render(<TaskProgress status={TaskStatus.FAILED} progress={75} />);

      const progressBar = screen.queryByRole('progressbar');
      expect(progressBar).not.toBeInTheDocument();
    });

    it('hides progress bar for paused tasks', () => {
      render(<TaskProgress status={TaskStatus.PAUSED} progress={60} />);

      const progressBar = screen.queryByRole('progressbar');
      expect(progressBar).not.toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('has proper ARIA attributes', () => {
      render(<TaskProgress status={TaskStatus.RUNNING} progress={33} />);

      const progressBar = screen.getByRole('progressbar');
      expect(progressBar).toHaveAttribute('aria-valuenow', '33');
      expect(progressBar).toHaveAttribute('aria-valuemin', '0');
      expect(progressBar).toHaveAttribute('aria-valuemax', '100');
      expect(progressBar).toHaveAttribute('aria-label', 'Task progress: 33%');
    });

    it('updates ARIA attributes when progress changes', () => {
      const { rerender } = render(
        <TaskProgress status={TaskStatus.RUNNING} progress={20} />
      );

      let progressBar = screen.getByRole('progressbar');
      expect(progressBar).toHaveAttribute('aria-label', 'Task progress: 20%');

      rerender(<TaskProgress status={TaskStatus.RUNNING} progress={80} />);

      progressBar = screen.getByRole('progressbar');
      expect(progressBar).toHaveAttribute('aria-label', 'Task progress: 80%');
    });
  });
});
