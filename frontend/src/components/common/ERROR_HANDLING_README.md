# Error Handling and Loading States

This document describes the error handling and loading state components available in the application.

## Error Boundaries

### ErrorBoundary

Global error boundary component that catches JavaScript errors anywhere in the component tree.

**Usage:**

```tsx
import { ErrorBoundary } from '../components/common';

// App-level error boundary
<ErrorBoundary level="app">
  <App />
</ErrorBoundary>

// Page-level error boundary
<ErrorBoundary level="page">
  <MyPage />
</ErrorBoundary>

// Component-level error boundary
<ErrorBoundary level="component">
  <MyComponent />
</ErrorBoundary>
```

**Props:**

- `level`: 'app' | 'page' | 'component' - Determines the error display style
- `fallback`: Custom fallback UI to display on error
- `onReset`: Callback function when user clicks "Try Again"
- `onError`: Callback function when an error is caught

**Features:**

- Displays user-friendly error messages
- Shows component stack trace in development mode
- Provides "Try Again" and "Go to Dashboard" recovery actions
- Integrates with error reporting services (future)

### PageErrorBoundary

Specialized error boundary for page-level errors with automatic navigation support.

**Usage:**

```tsx
import { PageErrorBoundary } from '../components/common';

function MyPage() {
  return (
    <PageErrorBoundary>
      <PageContent />
    </PageErrorBoundary>
  );
}
```

## Loading States

### LoadingSpinner

Simple loading spinner with optional message.

**Usage:**

```tsx
import { LoadingSpinner } from '../components/common';

// Basic spinner
<LoadingSpinner />

// With message
<LoadingSpinner message="Loading data..." />

// Full screen
<LoadingSpinner message="Loading..." fullScreen />

// Custom size
<LoadingSpinner size={60} />
```

**Props:**

- `message`: Optional loading message
- `size`: Spinner size in pixels (default: 40)
- `fullScreen`: Display in full screen mode (default: false)

### SkeletonLoader

Skeleton loading placeholders for different UI patterns.

**Usage:**

```tsx
import { SkeletonLoader } from '../components/common';

// Card skeleton
<SkeletonLoader variant="card" count={3} />

// List skeleton
<SkeletonLoader variant="list" count={5} />

// Detail page skeleton
<SkeletonLoader variant="detail" />

// Table skeleton
<SkeletonLoader variant="table" count={10} />
```

**Props:**

- `variant`: 'card' | 'list' | 'detail' | 'table'
- `count`: Number of skeleton items to display (default: 3)

**When to use:**

- Use skeleton loaders when loading data that will replace the skeleton
- Provides better perceived performance than spinners
- Maintains layout stability during loading

### ButtonLoadingSpinner

Small loading spinner for use inside buttons.

**Usage:**

```tsx
import { ButtonLoadingSpinner } from '../components/common';
import { Button } from '@mui/material';

<Button disabled={isLoading}>
  {isLoading ? <ButtonLoadingSpinner /> : 'Submit'}
</Button>;
```

**Props:**

- `size`: Spinner size in pixels (default: 20)
- `color`: 'inherit' | 'primary' | 'secondary' (default: 'inherit')

### ProgressIndicatorWithLabel

Progress indicator for long-running operations.

**Usage:**

```tsx
import { ProgressIndicatorWithLabel } from '../components/common';

// Linear progress
<ProgressIndicatorWithLabel
  value={progress}
  label="Processing..."
  showPercentage
/>

// Circular progress
<ProgressIndicatorWithLabel
  value={progress}
  variant="circular"
  showPercentage
/>

// With custom color
<ProgressIndicatorWithLabel
  value={progress}
  color="success"
/>
```

**Props:**

- `value`: Progress value (0-100)
- `label`: Optional label text
- `variant`: 'linear' | 'circular' (default: 'linear')
- `showPercentage`: Show percentage text (default: true)
- `color`: Progress bar color

## Toast Notifications

### ToastProvider

Context provider for toast notifications.

**Setup:**

```tsx
import { ToastProvider } from '../components/common';

function App() {
  return (
    <ToastProvider maxToasts={3} defaultDuration={6000}>
      <YourApp />
    </ToastProvider>
  );
}
```

**Props:**

- `maxToasts`: Maximum number of toasts to display (default: 3)
- `defaultDuration`: Default duration in milliseconds (default: 6000)

### useToast Hook

Hook for showing toast notifications.

**Usage:**

```tsx
import { useToast } from '../components/common';

function MyComponent() {
  const toast = useToast();

  const handleSuccess = () => {
    toast.showSuccess('Operation completed successfully');
  };

  const handleError = () => {
    toast.showError('An error occurred');
  };

  const handleWarning = () => {
    toast.showWarning('Please review your input');
  };

  const handleInfo = () => {
    toast.showInfo('New feature available');
  };

  return <Button onClick={handleSuccess}>Show Success</Button>;
}
```

**Methods:**

- `showSuccess(message, duration?)`: Show success toast
- `showError(message, duration?)`: Show error toast (stays longer by default)
- `showWarning(message, duration?)`: Show warning toast
- `showInfo(message, duration?)`: Show info toast
- `showToast(message, severity, duration?)`: Generic toast method

### useMutationToast Hook

Helper hook for showing toast notifications for mutations.

**Usage:**

```tsx
import { useMutationToast } from '../hooks/useMutationToast';

function MyComponent() {
  const { showMutationToast } = useMutationToast();

  const createMutation = useMutation({
    mutationFn: createItem,
    ...showMutationToast.create('Item'),
  });

  const updateMutation = useMutation({
    mutationFn: updateItem,
    ...showMutationToast.update('Item'),
  });

  const deleteMutation = useMutation({
    mutationFn: deleteItem,
    ...showMutationToast.delete('Item'),
  });

  return <div>...</div>;
}
```

**Methods:**

- `showMutationToast.create(entityName, options?)`: Toast handlers for create operations
- `showMutationToast.update(entityName, options?)`: Toast handlers for update operations
- `showMutationToast.delete(entityName, options?)`: Toast handlers for delete operations
- `showMutationToast.action(actionName, options?)`: Toast handlers for custom actions

## Form Validation

### FormFieldError

Component for displaying field-level validation errors.

**Usage:**

```tsx
import { FormFieldError } from '../components/common';
import { TextField } from '@mui/material';

<TextField
  label="Email"
  value={email}
  onChange={handleChange}
  error={Boolean(errors.email && touched.email)}
/>
<FormFieldError error={errors.email} touched={touched.email} />
```

**Props:**

- `error`: Error message string
- `touched`: Whether the field has been touched

### FormErrorSummary

Component for displaying form-level validation errors.

**Usage:**

```tsx
import { FormErrorSummary } from '../components/common';

<FormErrorSummary errors={errors} title="Please fix the following errors:" />;
```

**Props:**

- `errors`: Object with field names as keys and error messages as values
- `title`: Summary title (default: "Please fix the following errors:")

### ValidatedTextField

TextField component with integrated validation.

**Usage:**

```tsx
import { ValidatedTextField } from '../components/common';

<ValidatedTextField
  label="Email"
  value={email}
  onChange={handleChange}
  error={errors.email}
  touched={touched.email}
  onBlurValidation={(value) => validateField('email', value)}
  onChangeValidation={(value) => validateField('email', value)}
/>;
```

**Props:**

- All standard TextField props
- `error`: Error message string
- `touched`: Whether the field has been touched
- `onBlurValidation`: Validation function called on blur
- `onChangeValidation`: Validation function called on change

### useFormValidation Hook

Hook for form validation using Zod schemas.

**Usage:**

```tsx
import { useFormValidation } from '../hooks/useFormValidation';
import { z } from 'zod';

const schema = z.object({
  email: z.string().email('Invalid email address'),
  password: z.string().min(8, 'Password must be at least 8 characters'),
});

function MyForm() {
  const [values, setValues] = useState({ email: '', password: '' });

  const { errors, touched, isValid, validateForm, handleBlur, handleChange } =
    useFormValidation({
      schema,
      validateOnBlur: true,
      validateOnChange: false,
    });

  const handleSubmit = (e) => {
    e.preventDefault();
    if (validateForm(values)) {
      // Submit form
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <ValidatedTextField
        label="Email"
        value={values.email}
        onChange={(e) => {
          setValues({ ...values, email: e.target.value });
          handleChange('email', e.target.value);
        }}
        onBlur={(e) => handleBlur('email', e.target.value)}
        error={errors.email}
        touched={touched.email}
      />
      <Button type="submit">Submit</Button>
    </form>
  );
}
```

**Options:**

- `schema`: Zod schema for validation
- `validateOnBlur`: Validate field on blur (default: true)
- `validateOnChange`: Validate field on change (default: false)

**Returns:**

- `errors`: Object with field errors
- `touched`: Object with touched fields
- `isValid`: Whether the form is valid
- `validateField(field, value)`: Validate a single field
- `validateForm(values)`: Validate entire form
- `handleBlur(field, value)`: Blur event handler
- `handleChange(field, value)`: Change event handler
- `resetValidation()`: Reset validation state
- `setFieldTouched(field, touched)`: Set field touched state
- `setFieldError(field, error)`: Set field error

## Best Practices

### Error Boundaries

1. **Use at multiple levels**: Wrap the entire app, individual pages, and critical components
2. **Provide recovery actions**: Always give users a way to recover from errors
3. **Log errors**: Integrate with error reporting services in production
4. **Custom fallbacks**: Provide context-specific error messages when possible

### Loading States

1. **Use skeleton loaders for content**: Better perceived performance than spinners
2. **Show progress for long operations**: Use progress indicators for operations > 3 seconds
3. **Disable actions during loading**: Prevent duplicate submissions
4. **Provide feedback**: Always show loading state for async operations

### Toast Notifications

1. **Keep messages concise**: 1-2 sentences maximum
2. **Use appropriate severity**: Success for confirmations, error for failures, warning for cautions
3. **Don't overuse**: Limit to important user actions
4. **Provide context**: Include what action succeeded/failed

### Form Validation

1. **Validate on blur**: Don't annoy users with immediate validation
2. **Show errors after touch**: Only show errors for fields the user has interacted with
3. **Provide clear messages**: Tell users exactly what's wrong and how to fix it
4. **Validate before submit**: Always validate the entire form before submission
5. **Handle server errors**: Display server-side validation errors appropriately

## Examples

### Complete Form with Validation

```tsx
import { useState } from 'react';
import { z } from 'zod';
import {
  ValidatedTextField,
  FormErrorSummary,
  ButtonLoadingSpinner,
  useToast,
} from '../components/common';
import { useFormValidation } from '../hooks/useFormValidation';
import { Button, Box } from '@mui/material';

const schema = z.object({
  name: z.string().min(1, 'Name is required'),
  email: z.string().email('Invalid email address'),
  password: z.string().min(8, 'Password must be at least 8 characters'),
});

function RegistrationForm() {
  const [values, setValues] = useState({ name: '', email: '', password: '' });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const toast = useToast();

  const { errors, touched, validateForm, handleBlur, handleChange } =
    useFormValidation({
      schema,
      validateOnBlur: true,
    });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validateForm(values)) {
      return;
    }

    setIsSubmitting(true);
    try {
      await registerUser(values);
      toast.showSuccess('Registration successful!');
    } catch (error) {
      toast.showError('Registration failed. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <FormErrorSummary errors={errors} />

      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        <ValidatedTextField
          label="Name"
          value={values.name}
          onChange={(e) => {
            setValues({ ...values, name: e.target.value });
            handleChange('name', e.target.value);
          }}
          onBlur={(e) => handleBlur('name', e.target.value)}
          error={errors.name}
          touched={touched.name}
        />

        <ValidatedTextField
          label="Email"
          type="email"
          value={values.email}
          onChange={(e) => {
            setValues({ ...values, email: e.target.value });
            handleChange('email', e.target.value);
          }}
          onBlur={(e) => handleBlur('email', e.target.value)}
          error={errors.email}
          touched={touched.email}
        />

        <ValidatedTextField
          label="Password"
          type="password"
          value={values.password}
          onChange={(e) => {
            setValues({ ...values, password: e.target.value });
            handleChange('password', e.target.value);
          }}
          onBlur={(e) => handleBlur('password', e.target.value)}
          error={errors.password}
          touched={touched.password}
        />

        <Button type="submit" variant="contained" disabled={isSubmitting}>
          {isSubmitting ? <ButtonLoadingSpinner /> : 'Register'}
        </Button>
      </Box>
    </form>
  );
}
```

### Page with Error Boundary and Loading State

```tsx
import { useState, useEffect } from 'react';
import {
  PageErrorBoundary,
  SkeletonLoader,
  useToast,
} from '../components/common';

function MyPage() {
  const [data, setData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const toast = useToast();

  useEffect(() => {
    fetchData()
      .then(setData)
      .catch((error) => {
        toast.showError('Failed to load data');
      })
      .finally(() => setIsLoading(false));
  }, []);

  if (isLoading) {
    return <SkeletonLoader variant="detail" />;
  }

  return (
    <PageErrorBoundary>
      <div>{/* Page content */}</div>
    </PageErrorBoundary>
  );
}
```
