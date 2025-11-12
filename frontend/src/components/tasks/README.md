# Task-Based Strategy Configuration Components

This directory contains shared UI components for the task-based strategy configuration feature.

## Directory Structure

```
tasks/
├── forms/          # Form input components
├── display/        # Display and visualization components
├── actions/        # Action buttons and dialogs
├── charts/         # Chart and data visualization components
└── index.ts        # Main export file
```

## Form Components (`forms/`)

### ConfigurationSelector

Dropdown selector for choosing strategy configurations with search functionality.

```tsx
import { ConfigurationSelector } from '@/components/tasks';

<ConfigurationSelector
  value={configId}
  onChange={setConfigId}
  configurations={configurations}
  isLoading={isLoading}
  required
/>;
```

### DateRangePicker

Date range picker with validation for start and end dates.

```tsx
import { DateRangePicker } from '@/components/tasks';

<DateRangePicker
  startDate={startDate}
  endDate={endDate}
  onStartDateChange={setStartDate}
  onEndDateChange={setEndDate}
  required
/>;
```

### InstrumentSelector

Single-select dropdown for choosing trading instrument.

```tsx
import { InstrumentSelector } from '@/components/tasks';

<InstrumentSelector
  value={instrument}
  onChange={setInstrument}
  maxSelections={10}
  required
/>;
```

### BalanceInput

Validated number input for balance/currency values.

```tsx
import { BalanceInput } from '@/components/tasks';

<BalanceInput
  value={balance}
  onChange={setBalance}
  currency="USD"
  min={0}
  required
/>;
```

### DataSourceSelector

Radio button group for selecting data source (PostgreSQL/Athena).

```tsx
import { DataSourceSelector } from '@/components/tasks';

<DataSourceSelector
  value={dataSource}
  onChange={setDataSource}
  showDescriptions
/>;
```

### Validation Schemas

Zod schemas for form validation.

```tsx
import { backtestTaskSchema, validateDateRange } from '@/components/tasks';

// Validate entire form
const result = backtestTaskSchema.safeParse(formData);

// Validate specific fields
const { isValid, error } = validateDateRange(startDate, endDate, true);
```

## Display Components (`display/`)

### StatusBadge

Colored badge showing task status with icon.

```tsx
import { StatusBadge } from '@/components/tasks';

<StatusBadge status={TaskStatus.RUNNING} size="small" />;
```

### MetricCard

Card component for displaying a single metric.

```tsx
import { MetricCard } from '@/components/tasks';

<MetricCard
  title="Total Return"
  value="+15.3%"
  icon={<TrendingUp />}
  color="success"
  trend="up"
/>;
```

### ProgressIndicator

Progress bar or circular indicator with percentage.

```tsx
import { ProgressIndicator } from '@/components/tasks';

<ProgressIndicator
  value={45}
  variant="linear"
  showPercentage
  estimatedTimeRemaining="2h 15m"
/>;
```

### ExecutionTimeline

Timeline view of task execution history.

```tsx
import { ExecutionTimeline } from '@/components/tasks';

<ExecutionTimeline executions={executions} maxItems={10} showMetrics />;
```

### ErrorDisplay

Formatted error message display with expandable details.

```tsx
import { ErrorDisplay } from '@/components/tasks';

<ErrorDisplay
  error={error}
  severity="error"
  showDetails
  onRetry={handleRetry}
/>;
```

## Action Components (`actions/`)

### TaskActionMenu

Dropdown menu with task lifecycle actions.

```tsx
import { TaskActionMenu } from '@/components/tasks';

<TaskActionMenu
  status={task.status}
  onStart={handleStart}
  onStop={handleStop}
  onCopy={handleCopy}
  onEdit={handleEdit}
  onDelete={handleDelete}
/>;
```

### CopyTaskDialog

Dialog for copying a task with a new name.

```tsx
import { CopyTaskDialog } from '@/components/tasks';

<CopyTaskDialog
  open={open}
  taskName={task.name}
  onConfirm={handleCopy}
  onCancel={handleCancel}
/>;
```

### DeleteTaskDialog

Confirmation dialog for deleting a task with warnings.

```tsx
import { DeleteTaskDialog } from '@/components/tasks';

<DeleteTaskDialog
  open={open}
  taskName={task.name}
  taskStatus={task.status}
  onConfirm={handleDelete}
  onCancel={handleCancel}
  hasExecutionHistory
/>;
```

### Keyboard Shortcuts

Hook for registering keyboard shortcuts.

```tsx
import { useKeyboardShortcuts, createTaskShortcuts } from '@/components/tasks';

const shortcuts = createTaskShortcuts({
  onStart: handleStart,
  onStop: handleStop,
  onCopy: handleCopy,
});

useKeyboardShortcuts({ shortcuts, enabled: true });
```

## Chart Components (`charts/`)

### EquityCurveChart

Line chart showing balance over time.

```tsx
import { EquityCurveChart } from '@/components/tasks';

<EquityCurveChart
  data={equityCurve}
  initialBalance={10000}
  height={400}
  showExport
  onExport={handleExport}
/>;
```

### MetricsGrid

Grid layout of metric cards.

```tsx
import { MetricsGrid } from '@/components/tasks';

<MetricsGrid metrics={executionMetrics} columns={3} isLoading={isLoading} />;
```

### TradeLogTable

Sortable, filterable table of trades.

```tsx
import { TradeLogTable } from '@/components/tasks';

<TradeLogTable
  trades={trades}
  showExport
  onExport={handleExport}
  defaultRowsPerPage={10}
/>;
```

## Usage Examples

### Complete Task Form

```tsx
import {
  ConfigurationSelector,
  DateRangePicker,
  InstrumentSelector,
  BalanceInput,
  DataSourceSelector,
  backtestTaskSchema,
} from '@/components/tasks';

function BacktestTaskForm() {
  const [formData, setFormData] = useState({
    config_id: '',
    start_time: null,
    end_time: null,
    instrument: '',
    initial_balance: '',
    data_source: DataSource.POSTGRESQL,
  });

  const handleSubmit = () => {
    const result = backtestTaskSchema.safeParse(formData);
    if (result.success) {
      // Submit form
    }
  };

  return (
    <form>
      <ConfigurationSelector
        value={formData.config_id}
        onChange={(value) => setFormData({ ...formData, config_id: value })}
        configurations={configurations}
        required
      />
      <DateRangePicker
        startDate={formData.start_time}
        endDate={formData.end_time}
        onStartDateChange={(date) =>
          setFormData({ ...formData, start_time: date })
        }
        onEndDateChange={(date) => setFormData({ ...formData, end_time: date })}
        required
      />
      <InstrumentSelector
        value={formData.instrument}
        onChange={(value) => setFormData({ ...formData, instrument: value })}
        required
      />
      <BalanceInput
        value={formData.initial_balance}
        onChange={(value) =>
          setFormData({ ...formData, initial_balance: value })
        }
        required
      />
      <DataSourceSelector
        value={formData.data_source}
        onChange={(value) => setFormData({ ...formData, data_source: value })}
      />
    </form>
  );
}
```

### Task Detail Page

```tsx
import {
  StatusBadge,
  MetricsGrid,
  EquityCurveChart,
  TradeLogTable,
  ExecutionTimeline,
  TaskActionMenu,
} from '@/components/tasks';

function TaskDetailPage({ task }) {
  return (
    <div>
      <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
        <Typography variant="h4">{task.name}</Typography>
        <Box sx={{ display: 'flex', gap: 2 }}>
          <StatusBadge status={task.status} />
          <TaskActionMenu
            status={task.status}
            onStart={handleStart}
            onStop={handleStop}
            onCopy={handleCopy}
          />
        </Box>
      </Box>

      <MetricsGrid metrics={task.latest_execution?.metrics} columns={3} />

      <EquityCurveChart
        data={task.latest_execution?.metrics?.equity_curve}
        initialBalance={task.initial_balance}
      />

      <TradeLogTable
        trades={task.latest_execution?.metrics?.trade_log}
        showExport
      />

      <ExecutionTimeline executions={task.execution_history} maxItems={10} />
    </div>
  );
}
```

## Styling

All components use Material-UI (MUI) v7 and follow the application's theme. Components are responsive and support dark mode.

## Accessibility

- All form components have proper labels and ARIA attributes
- Keyboard navigation is supported throughout
- Color contrast meets WCAG AA standards
- Screen reader friendly

## Testing

Components can be tested using React Testing Library:

```tsx
import { render, screen } from '@testing-library/react';
import { StatusBadge } from '@/components/tasks';
import { TaskStatus } from '@/types/common';

test('renders status badge', () => {
  render(<StatusBadge status={TaskStatus.RUNNING} />);
  expect(screen.getByText('Running')).toBeInTheDocument();
});
```
