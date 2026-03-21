type LogContext = Record<string, unknown> | undefined;

function normalizeArgs(message: string, context?: LogContext): unknown[] {
  return context ? [message, context] : [message];
}

export const logger = {
  debug(message: string, context?: LogContext): void {
    if (import.meta.env.DEV) {
      console.debug(...normalizeArgs(message, context));
    }
  },

  info(message: string, context?: LogContext): void {
    if (import.meta.env.DEV) {
      console.info(...normalizeArgs(message, context));
    }
  },

  warn(message: string, context?: LogContext): void {
    console.warn(...normalizeArgs(message, context));
  },

  error(message: string, context?: LogContext): void {
    console.error(...normalizeArgs(message, context));
  },
};
