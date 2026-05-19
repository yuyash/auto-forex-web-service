export function getConfigurationCopyErrorMessage(
  error: Error | null
): string | undefined {
  if (!error) return undefined;

  const candidate = error as {
    details?: unknown;
    message?: unknown;
  };

  if (
    candidate.details &&
    typeof candidate.details === 'object' &&
    !Array.isArray(candidate.details)
  ) {
    const details = candidate.details as Record<string, unknown>;
    const nameErrors = details.name;
    if (Array.isArray(nameErrors) && typeof nameErrors[0] === 'string') {
      return nameErrors[0];
    }
    if (typeof details.detail === 'string') {
      return details.detail;
    }
    if (typeof details.message === 'string') {
      return details.message;
    }
  }

  return typeof candidate.message === 'string' ? candidate.message : undefined;
}
