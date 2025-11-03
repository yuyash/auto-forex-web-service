# Shared Components

This directory contains reusable UI components used throughout the application.

## Components

### LoadingSpinner

A loading indicator component with optional message and full-screen mode.

**Props:**

- `message?: string` - Optional loading message to display
- `size?: number` - Size of the spinner (default: 40)
- `fullScreen?: boolean` - Whether to display in full-screen mode (default: false)

**Usage:**

```tsx
import { LoadingSpinner } from '@/components/common';

// Basic usage
<LoadingSpinner />

// With message
<LoadingSpinner message="Loading data..." />

// Full screen
<LoadingSpinner fullScreen message="Please wait..." />
```

### ErrorBoundary

A React error boundary component that catches JavaScript errors in child components.

**Props:**

- `children: ReactNode` - Child components to wrap
- `fallback?: ReactNode` - Optional custom fallback UI

**Usage:**

```tsx
import { ErrorBoundary } from '@/components/common';

<ErrorBoundary>
  <YourComponent />
</ErrorBoundary>

// With custom fallback
<ErrorBoundary fallback={<CustomErrorUI />}>
  <YourComponent />
</ErrorBoundary>
```

### ConfirmDialog

A confirmation dialog component for user actions.

**Props:**

- `open: boolean` - Whether the dialog is open
- `title: string` - Dialog title
- `message: string` - Confirmation message
- `confirmText?: string` - Confirm button text (default: "Confirm")
- `cancelText?: string` - Cancel button text (default: "Cancel")
- `onConfirm: () => void` - Callback when confirmed
- `onCancel: () => void` - Callback when cancelled
- `confirmColor?: 'primary' | 'secondary' | 'error' | 'warning' | 'info' | 'success'` - Confirm button color (default: "primary")

**Usage:**

```tsx
import { ConfirmDialog } from '@/components/common';

const [open, setOpen] = useState(false);

<ConfirmDialog
  open={open}
  title="Delete Account"
  message="Are you sure you want to delete this account?"
  confirmText="Delete"
  confirmColor="error"
  onConfirm={() => {
    // Handle deletion
    setOpen(false);
  }}
  onCancel={() => setOpen(false)}
/>;
```

### Toast

A toast notification system with context provider and hook.

**Setup:**

Wrap your app with `ToastProvider`:

```tsx
import { ToastProvider } from '@/components/common';

<ToastProvider>
  <App />
</ToastProvider>;
```

**Usage:**

```tsx
import { useToast } from '@/components/common';

const MyComponent = () => {
  const { showSuccess, showError, showWarning, showInfo } = useToast();

  const handleAction = () => {
    try {
      // Do something
      showSuccess('Action completed successfully!');
    } catch (error) {
      showError('Action failed!');
    }
  };

  return <button onClick={handleAction}>Do Action</button>;
};
```

**Methods:**

- `showToast(message, severity?, duration?)` - Show a toast with custom severity
- `showSuccess(message, duration?)` - Show success toast
- `showError(message, duration?)` - Show error toast
- `showWarning(message, duration?)` - Show warning toast
- `showInfo(message, duration?)` - Show info toast

### DataTable

A feature-rich data table component with sorting, filtering, and pagination.

**Props:**

- `columns: Column<T>[]` - Column definitions
- `data: T[]` - Data array
- `rowsPerPageOptions?: number[]` - Rows per page options (default: [10, 25, 50, 100])
- `defaultRowsPerPage?: number` - Default rows per page (default: 10)
- `onRowClick?: (row: T) => void` - Callback when row is clicked
- `emptyMessage?: string` - Message when no data (default: "No data available")
- `stickyHeader?: boolean` - Whether header is sticky (default: true)

**Column Definition:**

```typescript
interface Column<T> {
  id: keyof T | string; // Column identifier
  label: string; // Column header label
  sortable?: boolean; // Enable sorting
  filterable?: boolean; // Enable filtering
  render?: (row: T) => React.ReactNode; // Custom cell renderer
  align?: 'left' | 'center' | 'right'; // Cell alignment
  minWidth?: number; // Minimum column width
}
```

**Usage:**

```tsx
import { DataTable, Column } from '@/components/common';

interface User {
  id: number;
  name: string;
  email: string;
  status: string;
}

const columns: Column<User>[] = [
  { id: 'id', label: 'ID', sortable: true },
  { id: 'name', label: 'Name', sortable: true, filterable: true },
  { id: 'email', label: 'Email', filterable: true },
  {
    id: 'status',
    label: 'Status',
    sortable: true,
    render: (row) => (
      <Chip
        label={row.status}
        color={row.status === 'active' ? 'success' : 'default'}
      />
    ),
  },
];

const users: User[] = [
  { id: 1, name: 'John Doe', email: 'john@example.com', status: 'active' },
  // ... more users
];

<DataTable
  columns={columns}
  data={users}
  onRowClick={(user) => console.log('Clicked:', user)}
  defaultRowsPerPage={25}
/>;
```

### LanguageSelector

A language selector component for switching between English and Japanese.

**Usage:**

```tsx
import { LanguageSelector } from '@/components/common';

<LanguageSelector />;
```

## Testing

All components have comprehensive test coverage. Run tests with:

```bash
npm run test
```

## Code Quality

All components follow the project's code quality standards:

- Formatted with Prettier
- Linted with ESLint
- Type-checked with TypeScript
- Tested with Vitest and React Testing Library
