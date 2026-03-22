import { z } from 'zod';

export function readStoredValue<T>(
  key: string,
  schema: z.ZodType<T>,
  fallback: T
): T {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) {
      return fallback;
    }
    const parsed = JSON.parse(raw);
    return schema.parse(parsed);
  } catch {
    return fallback;
  }
}

export function readStoredStringValue<T extends string>(
  key: string,
  schema: z.ZodType<T>,
  fallback: T
): T {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) {
      return fallback;
    }
    try {
      return schema.parse(JSON.parse(raw));
    } catch {
      return schema.parse(raw);
    }
  } catch {
    return fallback;
  }
}

export function writeStoredValue<T>(key: string, value: T): void {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // ignore storage write failures
  }
}

export function writeStoredStringValue(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch {
    // ignore storage write failures
  }
}

export function removeStoredValue(key: string): void {
  try {
    localStorage.removeItem(key);
  } catch {
    // ignore storage removal failures
  }
}
