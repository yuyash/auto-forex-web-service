import { Alert } from '@mui/material';
import React from 'react';

interface TaskTrendAlertsProps {
  candleErrorMessage: string | null;
  candleErrorSeverity: 'info' | 'error';
  errorCode?: string | null;
  usingGranularityFallback: boolean;
  errorMessage: string | null;
  warningMessage: string | null;
  chartWarning: string | null;
  t: (key: string, options?: Record<string, unknown>) => string;
}

export function TaskTrendAlerts({
  candleErrorMessage,
  candleErrorSeverity,
  errorCode,
  usingGranularityFallback,
  errorMessage,
  warningMessage,
  chartWarning,
  t,
}: TaskTrendAlertsProps) {
  return (
    <>
      {candleErrorMessage && (
        <Alert
          severity={
            errorCode === 'NO_OANDA_ACCOUNT' ? 'info' : candleErrorSeverity
          }
          sx={{ mb: 1 }}
        >
          {candleErrorMessage}
        </Alert>
      )}
      {usingGranularityFallback && (
        <Alert severity="warning" sx={{ mb: 1 }}>
          {t('tables.trend.granularityFallbackWarning')}
        </Alert>
      )}
      {errorMessage && (
        <Alert severity="warning" sx={{ mb: 1 }}>
          {t('tables.trend.replayRefreshFailed', {
            defaultValue: errorMessage,
          })}
        </Alert>
      )}
      {warningMessage && (
        <Alert severity="info" sx={{ mb: 1 }}>
          {warningMessage}
        </Alert>
      )}
      {chartWarning && (
        <Alert severity="warning" sx={{ mb: 1 }}>
          {t('tables.trend.chartRenderFailed', {
            defaultValue: chartWarning,
          })}
        </Alert>
      )}
    </>
  );
}
