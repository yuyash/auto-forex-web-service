import { logger } from '../../utils/logger';

export interface ErrorReportContext {
  componentStack?: string;
  level?: 'app' | 'page' | 'component';
  metadata?: Record<string, unknown>;
}

declare global {
  interface Window {
    __APP_ERROR_REPORTER__?: (payload: Record<string, unknown>) => void;
  }
}

function buildPayload(
  error: Error,
  context: ErrorReportContext
): Record<string, unknown> {
  return {
    message: error.message,
    stack: error.stack,
    level: context.level ?? 'component',
    componentStack: context.componentStack,
    metadata: context.metadata ?? {},
    timestamp: new Date().toISOString(),
    userAgent:
      typeof navigator !== 'undefined' ? navigator.userAgent : 'unknown',
    url: typeof window !== 'undefined' ? window.location.href : 'unknown',
  };
}

function sendToEndpoint(
  endpoint: string,
  payload: Record<string, unknown>
): void {
  const body = JSON.stringify(payload);

  if (
    typeof navigator !== 'undefined' &&
    typeof navigator.sendBeacon === 'function'
  ) {
    const blob = new Blob([body], { type: 'application/json' });
    navigator.sendBeacon(endpoint, blob);
    return;
  }

  void fetch(endpoint, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body,
    keepalive: true,
  }).catch((reportingError) => {
    logger.warn('Failed to send frontend error report', {
      error:
        reportingError instanceof Error
          ? reportingError.message
          : String(reportingError),
    });
  });
}

export function reportFrontendError(
  error: Error,
  context: ErrorReportContext = {}
): void {
  const payload = buildPayload(error, context);
  const endpoint = import.meta.env.VITE_ERROR_REPORTING_ENDPOINT;

  if (
    typeof window !== 'undefined' &&
    typeof window.__APP_ERROR_REPORTER__ === 'function'
  ) {
    window.__APP_ERROR_REPORTER__(payload);
    return;
  }

  if (endpoint) {
    sendToEndpoint(endpoint, payload);
    return;
  }

  if (import.meta.env.PROD) {
    logger.warn('Frontend error captured without reporting endpoint', payload);
  }
}
