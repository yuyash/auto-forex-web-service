/**
 * Integration tests for useFormValidation hook.
 * Verifies Zod-based validation, blur/change handlers, and error state.
 */

import { describe, it, expect } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { z } from 'zod';
import { useFormValidation } from '../../../src/hooks/useFormValidation';

const schema = z.object({
  email: z.string().email('Invalid email'),
  name: z.string().min(2, 'Name too short'),
  age: z.number().min(0, 'Must be positive'),
});

type FormData = z.infer<typeof schema>;

describe('useFormValidation', () => {
  it('starts with no errors and isValid true', () => {
    const { result } = renderHook(() =>
      useFormValidation<FormData>({ schema })
    );
    expect(result.current.errors).toEqual({});
    expect(result.current.isValid).toBe(true);
  });

  it('validateForm sets errors for invalid data', () => {
    const { result } = renderHook(() =>
      useFormValidation<FormData>({ schema })
    );

    act(() => {
      result.current.validateForm({
        email: 'bad',
        name: 'a',
        age: -1,
      } as FormData);
    });

    expect(result.current.errors.email).toBe('Invalid email');
    expect(result.current.errors.name).toBe('Name too short');
    expect(result.current.errors.age).toBe('Must be positive');
    expect(result.current.isValid).toBe(false);
  });

  it('validateForm returns true for valid data', () => {
    const { result } = renderHook(() =>
      useFormValidation<FormData>({ schema })
    );

    let isValid: boolean;
    act(() => {
      isValid = result.current.validateForm({
        email: 'test@example.com',
        name: 'John',
        age: 25,
      } as FormData);
    });

    expect(isValid!).toBe(true);
    expect(result.current.errors).toEqual({});
    expect(result.current.isValid).toBe(true);
  });

  it('validateField validates a single field', () => {
    const { result } = renderHook(() =>
      useFormValidation<FormData>({ schema })
    );

    act(() => {
      result.current.validateField('email', 'not-an-email');
    });

    expect(result.current.errors.email).toBe('Invalid email');
  });

  it('handleBlur marks field as touched and validates', () => {
    const { result } = renderHook(() =>
      useFormValidation<FormData>({ schema, validateOnBlur: true })
    );

    act(() => {
      result.current.handleBlur('email', 'bad');
    });

    expect(result.current.touched.email).toBe(true);
    expect(result.current.errors.email).toBe('Invalid email');
  });

  it('handleChange validates only touched fields when validateOnChange is true', () => {
    const { result } = renderHook(() =>
      useFormValidation<FormData>({ schema, validateOnChange: true })
    );

    // Field not touched yet — should not validate
    act(() => {
      result.current.handleChange('email', 'bad');
    });
    expect(result.current.errors.email).toBeUndefined();

    // Touch the field
    act(() => {
      result.current.setFieldTouched('email', true);
    });

    // Now change should trigger validation
    act(() => {
      result.current.handleChange('email', 'still-bad');
    });
    expect(result.current.errors.email).toBe('Invalid email');
  });

  it('resetValidation clears all state', () => {
    const { result } = renderHook(() =>
      useFormValidation<FormData>({ schema })
    );

    act(() => {
      result.current.validateForm({
        email: 'bad',
        name: 'a',
        age: -1,
      } as FormData);
      result.current.setFieldTouched('email', true);
    });

    expect(result.current.isValid).toBe(false);

    act(() => {
      result.current.resetValidation();
    });

    expect(result.current.errors).toEqual({});
    expect(result.current.touched).toEqual({});
    expect(result.current.isValid).toBe(true);
  });

  it('setFieldError sets a custom error', () => {
    const { result } = renderHook(() =>
      useFormValidation<FormData>({ schema })
    );

    act(() => {
      result.current.setFieldError('email', 'Already taken');
    });

    expect(result.current.errors.email).toBe('Already taken');
    expect(result.current.isValid).toBe(false);
  });
});
