import { Box, Typography, Paper } from '@mui/material';
import { useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { lazy, Suspense } from 'react';
import type { BacktestTaskUpdateFormProps } from '../components/backtest/BacktestTaskUpdateForm';
import { useBacktestTask } from '../hooks/useBacktestTasks';
import type { BacktestInitialPositionCycle } from '../types/backtestTask';
import {
  LoadingSpinner,
  Breadcrumbs,
  PageContainer,
} from '../components/common';

const BacktestTaskForm = lazy(
  () => import('../components/backtest/BacktestTaskForm')
);
const BacktestTaskUpdateForm = lazy(
  () => import('../components/backtest/BacktestTaskUpdateForm')
);

type BacktestTaskUpdateInitialData = BacktestTaskUpdateFormProps['initialData'];

function numericValue(value: unknown): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function optionalNumericValue(value: unknown): number | null | undefined {
  if (value === null) return null;
  if (value === undefined || value === '') return undefined;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function normalizeInitialPositionCycles(
  cycles: BacktestInitialPositionCycle[] | undefined
): BacktestTaskUpdateInitialData['initial_position_cycles'] {
  return (cycles ?? []).map((cycle) => ({
    direction: cycle.direction,
    positions: cycle.positions.map((position) => ({
      layer_number: numericValue(position.layer_number),
      retracement_count: numericValue(position.retracement_count),
      units: numericValue(position.units),
      entry_price: numericValue(position.entry_price),
      planned_exit_price: optionalNumericValue(position.planned_exit_price),
      stop_loss_price: optionalNumericValue(position.stop_loss_price),
      status: position.status ?? 'open',
      exit_price: optionalNumericValue(position.exit_price),
      close_reason: position.close_reason,
    })),
  }));
}

function FormLoadingFallback() {
  return (
    <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
      <LoadingSpinner />
    </Box>
  );
}

export default function BacktestTaskFormPage() {
  const { t } = useTranslation('backtest');
  const { id } = useParams<{ id: string }>();
  const taskId = id || undefined;

  const { data: task, isLoading } = useBacktestTask(taskId);
  const updateInitialData: BacktestTaskUpdateInitialData | null = task
    ? {
        config_id: task.config_id,
        data_source: task.data_source,
        start_time: task.start_time,
        end_time: task.end_time,
        initial_balance: parseFloat(task.initial_balance),
        account_currency: task.account_currency ?? 'USD',
        display_currency:
          task.display_currency ?? task.account_currency ?? 'USD',
        commission_per_trade: parseFloat(task.commission_per_trade),
        pip_size: task.pip_size ? parseFloat(task.pip_size) : undefined,
        instrument: task.instrument,
        tick_granularity:
          task.tick_granularity as BacktestTaskUpdateInitialData['tick_granularity'],
        tick_window_value_mode:
          task.tick_window_value_mode as BacktestTaskUpdateInitialData['tick_window_value_mode'],
        sell_at_completion:
          task.sell_on_stop ?? task.sell_at_completion ?? false,
        hedging_enabled: task.hedging_enabled ?? true,
        drain_duration_hours: task.drain_duration_hours,
        market_idle_pre_close_minutes: task.market_idle_pre_close_minutes,
        market_idle_resume_delay_minutes: task.market_idle_resume_delay_minutes,
        market_close_enabled: task.market_close_enabled ?? false,
        market_close_weekday: task.market_close_weekday,
        market_close_hour_utc: task.market_close_hour_utc,
        market_open_weekday: task.market_open_weekday,
        market_open_hour_utc: task.market_open_hour_utc,
        max_tick_gap_hours: task.max_tick_gap_hours,
        holidays_enabled: task.holidays_enabled ?? false,
        excluded_dates: task.excluded_dates ?? [],
        initial_positions_enabled: task.initial_positions_enabled ?? false,
        initial_position_cycles: normalizeInitialPositionCycles(
          task.initial_position_cycles
        ),
        in_memory_mode: task.in_memory_mode ?? false,
      }
    : null;

  if (taskId && (isLoading || !task)) {
    return (
      <PageContainer>
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            minHeight: '60vh',
          }}
        >
          <LoadingSpinner />
        </Box>
      </PageContainer>
    );
  }

  return (
    <PageContainer>
      <Box sx={{ py: 4 }}>
        <Breadcrumbs />

        <Typography variant="h4" component="h1" gutterBottom>
          {taskId ? t('pages.editTitle') : t('pages.createTitle')}
        </Typography>

        <Paper sx={{ p: { xs: 2, sm: 3 }, mt: 3 }}>
          <Suspense fallback={<FormLoadingFallback />}>
            {taskId && task ? (
              <BacktestTaskUpdateForm
                taskId={taskId}
                taskName={task.name}
                taskDescription={task.description}
                debugOptions={task.debug_options}
                restartRequiredForExecutionEdits={
                  task.action_policy?.restart_required_for_execution_edits
                }
                initialData={updateInitialData!}
              />
            ) : (
              <BacktestTaskForm />
            )}
          </Suspense>
        </Paper>
      </Box>
    </PageContainer>
  );
}
