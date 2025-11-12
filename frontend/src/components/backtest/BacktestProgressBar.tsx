import { useEffect, useState, useCallback } from 'react';
import {
  Box,
  LinearProgress,
  Typography,
  Paper,
  Alert,
  CircularProgress,
} from '@mui/material';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../contexts/AuthContext';
import type { Backtest } from '../../types/backtest';

interface BacktestProgressBarProps {
  backtestId: number | null;
  onComplete?: (backtest: Backtest) => void;
  onError?: (error: string) => void;
}

const BacktestProgressBar = ({
  backtestId,
  onComplete,
  onError,
}: BacktestProgressBarProps) => {
  const { t } = useTranslation(['backtest', 'common']);
  const { token } = useAuth();
  const [backtest, setBacktest] = useState<Backtest | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [startTime, setStartTime] = useState<number | null>(null);
  const [estimatedTimeRemaining, setEstimatedTimeRemaining] = useState<
    string | null
  >(null);

  // Fetch backtest status
  const fetchBacktestStatus = useCallback(async () => {
    if (!backtestId || !token) return;

    try {
      setLoading(true);
      setError(null);

      const response = await fetch(`/api/backtest/${backtestId}/status`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error('Failed to fetch backtest status');
      }

      const data = await response.json();
      setBacktest(data);

      // Calculate estimated time remaining
      if (data.status === 'running' && data.progress > 0) {
        if (!startTime) {
          setStartTime(Date.now());
        } else {
          const elapsed = Date.now() - startTime;
          const progressPercent = data.progress / 100;
          const totalEstimated = elapsed / progressPercent;
          const remaining = totalEstimated - elapsed;

          if (remaining > 0) {
            const minutes = Math.floor(remaining / 60000);
            const seconds = Math.floor((remaining % 60000) / 1000);
            setEstimatedTimeRemaining(
              minutes > 0 ? `${minutes}m ${seconds}s` : `${seconds}s`
            );
          }
        }
      }

      // Handle completion
      if (data.status === 'completed' && onComplete) {
        onComplete(data);
      }

      // Handle failure
      if (data.status === 'failed') {
        const errorMsg = t(
          'backtest:progress.failed',
          'Backtest failed to complete'
        );
        setError(errorMsg);
        if (onError) {
          onError(errorMsg);
        }
      }
    } catch (err) {
      const errorMsg =
        err instanceof Error ? err.message : 'Failed to fetch backtest status';
      setError(errorMsg);
      if (onError) {
        onError(errorMsg);
      }
    } finally {
      setLoading(false);
    }
  }, [backtestId, token, startTime, onComplete, onError, t]);

  // Poll for status updates
  useEffect(() => {
    if (!backtestId) {
      setBacktest(null);
      setStartTime(null);
      setEstimatedTimeRemaining(null);
      return;
    }

    // Initial fetch
    fetchBacktestStatus();

    // Poll every 2 seconds while running
    const interval = setInterval(() => {
      if (backtest?.status === 'running' || backtest?.status === 'pending') {
        fetchBacktestStatus();
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [backtestId, backtest?.status, fetchBacktestStatus]);

  // Don't render if no backtest ID
  if (!backtestId) {
    return (
      <Paper sx={{ p: 3 }}>
        <Typography variant="body2" color="text.secondary">
          {t(
            'backtest:progress.noBacktest',
            'No backtest running. Configure and start a backtest to see progress.'
          )}
        </Typography>
      </Paper>
    );
  }

  // Loading state
  if (loading && !backtest) {
    return (
      <Paper sx={{ p: 3 }}>
        <Box display="flex" alignItems="center" gap={2}>
          <CircularProgress size={24} />
          <Typography variant="body2">
            {t('common:loading', 'Loading...')}
          </Typography>
        </Box>
      </Paper>
    );
  }

  // Error state
  if (error) {
    return (
      <Paper sx={{ p: 3 }}>
        <Alert severity="error">{error}</Alert>
      </Paper>
    );
  }

  // No backtest data
  if (!backtest) {
    return (
      <Paper sx={{ p: 3 }}>
        <Typography variant="body2" color="text.secondary">
          {t('backtest:progress.notFound', 'Backtest not found')}
        </Typography>
      </Paper>
    );
  }

  return (
    <Paper sx={{ p: 3 }}>
      <Typography variant="h6" gutterBottom>
        {t('backtest:progress.title', 'Backtest Progress')}
      </Typography>

      {/* Status */}
      <Box sx={{ mb: 2 }}>
        <Typography variant="body2" color="text.secondary" gutterBottom>
          {t('backtest:progress.status', 'Status')}:{' '}
          <Typography
            component="span"
            variant="body2"
            fontWeight="medium"
            color={
              backtest.status === 'completed'
                ? 'success.main'
                : backtest.status === 'failed'
                  ? 'error.main'
                  : backtest.status === 'running'
                    ? 'primary.main'
                    : 'text.secondary'
            }
          >
            {t(`backtest:progress.statusValues.${backtest.status}`, {
              defaultValue:
                backtest.status.charAt(0).toUpperCase() +
                backtest.status.slice(1),
            })}
          </Typography>
        </Typography>
      </Box>

      {/* Progress Bar */}
      {(backtest.status === 'running' || backtest.status === 'pending') && (
        <Box sx={{ mb: 2 }}>
          <Box
            display="flex"
            justifyContent="space-between"
            alignItems="center"
            mb={1}
          >
            <Typography variant="body2" color="text.secondary">
              {t('backtest:progress.progress', 'Progress')}
            </Typography>
            <Typography variant="body2" fontWeight="medium">
              {backtest.progress.toFixed(1)}%
            </Typography>
          </Box>
          <LinearProgress
            variant="determinate"
            value={backtest.progress}
            sx={{ height: 8, borderRadius: 1 }}
          />
        </Box>
      )}

      {/* Estimated Time Remaining */}
      {backtest.status === 'running' && estimatedTimeRemaining && (
        <Box sx={{ mb: 2 }}>
          <Typography variant="body2" color="text.secondary">
            {t(
              'backtest:progress.estimatedTimeRemaining',
              'Estimated time remaining'
            )}
            :{' '}
            <Typography component="span" variant="body2" fontWeight="medium">
              {estimatedTimeRemaining}
            </Typography>
          </Typography>
        </Box>
      )}

      {/* Backtest Details */}
      <Box sx={{ mt: 3, pt: 2, borderTop: 1, borderColor: 'divider' }}>
        <Typography variant="body2" color="text.secondary" gutterBottom>
          {t('backtest:progress.details', 'Details')}
        </Typography>
        <Box sx={{ display: 'grid', gap: 1, mt: 1 }}>
          <Typography variant="body2">
            <Typography component="span" color="text.secondary">
              {t('backtest:progress.strategy', 'Strategy')}:{' '}
            </Typography>
            {backtest.strategy_type}
          </Typography>
          <Typography variant="body2">
            <Typography component="span" color="text.secondary">
              {t('backtest:progress.instrument', 'Instrument')}:{' '}
            </Typography>
            {backtest.instrument}
          </Typography>
          <Typography variant="body2">
            <Typography component="span" color="text.secondary">
              {t('backtest:progress.dateRange', 'Date Range')}:{' '}
            </Typography>
            {backtest.start_date} - {backtest.end_date}
          </Typography>
          <Typography variant="body2">
            <Typography component="span" color="text.secondary">
              {t('backtest:progress.initialBalance', 'Initial Balance')}:{' '}
            </Typography>
            ${backtest.initial_balance.toLocaleString()}
          </Typography>
        </Box>
      </Box>

      {/* Completion Message */}
      {backtest.status === 'completed' && (
        <Alert severity="success" sx={{ mt: 2 }}>
          {t(
            'backtest:progress.completed',
            'Backtest completed successfully! View results below.'
          )}
        </Alert>
      )}

      {/* Failure Message */}
      {backtest.status === 'failed' && (
        <Alert severity="error" sx={{ mt: 2 }}>
          {t(
            'backtest:progress.failed',
            'Backtest failed to complete. Please try again.'
          )}
        </Alert>
      )}
    </Paper>
  );
};

export default BacktestProgressBar;
