export function firstValidationError(errors: unknown): string | null {
  if (!errors || typeof errors !== 'object') {
    return null;
  }

  if (Array.isArray(errors)) {
    for (const item of errors) {
      const message = firstValidationError(item);
      if (message) return message;
    }
    return null;
  }

  const record = errors as Record<string, unknown>;
  if (typeof record.message === 'string' && record.message.trim()) {
    return record.message;
  }

  for (const [key, value] of Object.entries(record)) {
    if (key === 'ref' || key === '_f') {
      continue;
    }
    const message = firstValidationError(value);
    if (message) return message;
  }

  return null;
}

export function hasValidationErrors(errors: unknown): boolean {
  if (!errors || typeof errors !== 'object') {
    return false;
  }

  if (Array.isArray(errors)) {
    return errors.some((item) => hasValidationErrors(item));
  }

  return Object.keys(errors as Record<string, unknown>).length > 0;
}
