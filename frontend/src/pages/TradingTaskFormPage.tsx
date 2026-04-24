import { Box, Typography, Paper } from '@mui/material';
import { useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import TradingTaskForm from '../components/trading/TradingTaskForm';
import TradingTaskUpdateForm from '../components/trading/TradingTaskUpdateForm';
import { useTradingTask } from '../hooks/useTradingTasks';
import {
  LoadingSpinner,
  Breadcrumbs,
  PageContainer,
} from '../components/common';

export default function TradingTaskFormPage() {
  const { t } = useTranslation('trading');
  const { id } = useParams<{ id: string }>();
  const taskId = id || undefined;

  const { data: task, isLoading } = useTradingTask(taskId, {
    enabled: !!taskId,
  });

  const isEditMode = !!taskId;

  if (isEditMode && (isLoading || !task)) {
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
          {isEditMode ? t('pages.editTitle') : t('pages.createTitle')}
        </Typography>
        <Typography variant="body1" color="text.secondary" sx={{ mb: 4 }}>
          {isEditMode ? t('pages.editSubtitle') : t('pages.createSubtitle')}
        </Typography>

        <Paper sx={{ p: 4, mt: 3 }}>
          {isEditMode && task ? (
            <TradingTaskUpdateForm
              taskId={taskId}
              taskName={task.name}
              taskDescription={task.description}
              accountId={Number(task.account_id)}
              accountName={task.account_name}
              debugOptions={task.debug_options}
              initialData={{
                config_id: task.config_id,
                hedging_enabled: task.hedging_enabled,
                api_retry_max_attempts: task.api_retry_max_attempts,
                api_retry_backoff_base_seconds:
                  task.api_retry_backoff_base_seconds
                    ? Number(task.api_retry_backoff_base_seconds)
                    : undefined,
                api_retry_backoff_max_seconds:
                  task.api_retry_backoff_max_seconds
                    ? Number(task.api_retry_backoff_max_seconds)
                    : undefined,
                drain_duration_hours: task.drain_duration_hours,
                market_idle_pre_close_minutes:
                  task.market_idle_pre_close_minutes,
                market_idle_resume_delay_minutes:
                  task.market_idle_resume_delay_minutes,
              }}
            />
          ) : (
            <TradingTaskForm />
          )}
        </Paper>
      </Box>
    </PageContainer>
  );
}
