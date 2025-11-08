import { useState, useCallback } from 'react';
import { z } from 'zod';

interface ValidationState<T> {
  errors: Partial<Record<keyof T, string>>;
  touched: Partial<Record<keyof T, boolean>>;
  isValid: boolean;
}

interface UseFormValidationOptions<T> {
  schema: z.ZodSchema<T>;
  validateOnBlur?: boolean;
  validateOnChange?: boolean;
}

/**
 * Hook for form validation using Zod schemas
 * Provides validation state and handlers for blur and change events
 */
export function useFormValidation<T extends Record<string, unknown>>({
  schema,
  validateOnBlur = true,
  validateOnChange = false,
}: UseFormValidationOptions<T>) {
  const [validationState, setValidationState] = useState<ValidationState<T>>({
    errors: {},
    touched: {},
    isValid: true,
  });

  const validateField = useCallback(
    (field: keyof T, value: unknown) => {
      try {
        // Validate single field
        if (schema instanceof z.ZodObject) {
          const fieldSchema = schema.shape[field as string];
          if (fieldSchema && typeof fieldSchema.parse === 'function') {
            fieldSchema.parse(value);
            setValidationState((prev) => ({
              ...prev,
              errors: { ...prev.errors, [field]: undefined },
            }));
            return true;
          }
        }
      } catch (error) {
        if (error instanceof z.ZodError) {
          const fieldError = error.issues[0]?.message;
          setValidationState((prev) => ({
            ...prev,
            errors: { ...prev.errors, [field]: fieldError },
            isValid: false,
          }));
          return false;
        }
      }
      return true;
    },
    [schema]
  );

  const validateForm = useCallback(
    (values: T) => {
      try {
        schema.parse(values);
        setValidationState({
          errors: {},
          touched: validationState.touched,
          isValid: true,
        });
        return true;
      } catch (error) {
        if (error instanceof z.ZodError) {
          const errors: Partial<Record<keyof T, string>> = {};
          error.issues.forEach((err: z.ZodIssue) => {
            const field = err.path[0] as keyof T;
            if (field) {
              errors[field] = err.message;
            }
          });
          setValidationState({
            errors,
            touched: validationState.touched,
            isValid: false,
          });
          return false;
        }
      }
      return false;
    },
    [schema, validationState.touched]
  );

  const handleBlur = useCallback(
    (field: keyof T, value: unknown) => {
      setValidationState((prev) => ({
        ...prev,
        touched: { ...prev.touched, [field]: true },
      }));

      if (validateOnBlur) {
        validateField(field, value);
      }
    },
    [validateOnBlur, validateField]
  );

  const handleChange = useCallback(
    (field: keyof T, value: unknown) => {
      if (validateOnChange && validationState.touched[field]) {
        validateField(field, value);
      }
    },
    [validateOnChange, validateField, validationState.touched]
  );

  const resetValidation = useCallback(() => {
    setValidationState({
      errors: {},
      touched: {},
      isValid: true,
    });
  }, []);

  const setFieldTouched = useCallback(
    (field: keyof T, touched: boolean = true) => {
      setValidationState((prev) => ({
        ...prev,
        touched: { ...prev.touched, [field]: touched },
      }));
    },
    []
  );

  const setFieldError = useCallback((field: keyof T, error: string) => {
    setValidationState((prev) => ({
      ...prev,
      errors: { ...prev.errors, [field]: error },
      isValid: false,
    }));
  }, []);

  return {
    errors: validationState.errors,
    touched: validationState.touched,
    isValid: validationState.isValid,
    validateField,
    validateForm,
    handleBlur,
    handleChange,
    resetValidation,
    setFieldTouched,
    setFieldError,
  };
}
