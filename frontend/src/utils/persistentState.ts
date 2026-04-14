import { z } from 'zod';

export const STORAGE_CHANGE_EVENT = 'app-storage-change';

function dispatchStorageChange(key: string): void {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(
    new CustomEvent(STORAGE_CHANGE_EVENT, {
      detail: { key },
    })
  );
}

export function readRawStoredValue(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

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
    dispatchStorageChange(key);
  } catch {
    // ignore storage write failures
  }
}

export function writeRawStoredValue(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
    dispatchStorageChange(key);
  } catch {
    // ignore storage write failures
  }
}

export function writeStoredStringValue(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
    dispatchStorageChange(key);
  } catch {
    // ignore storage write failures
  }
}

export function removeStoredValue(key: string): void {
  try {
    localStorage.removeItem(key);
    dispatchStorageChange(key);
  } catch {
    // ignore storage removal failures
  }
}
