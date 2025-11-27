import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import BacktestTaskForm from '../components/backtest/BacktestTaskForm';
import { DataSource } from '../types/common';

// Mock react-router-dom navigate
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

// Create mock functions that can be accessed in tests
const mockCreateMutate = vi.fn();
const mockUpdateMutate = vi.fn();

// Mock the hooks
vi.mock('../hooks/useBacktestTaskMutations', () => ({
  useCreateBacktestTask: () => ({
    mutate: mockCreateMutate,
    isLoading: false,
  }),
  useUpdateBacktestTask: () => ({
    mutate: mockUpdateMutate,
    isLoading: false,
  }),
}));

vi.mock('../hooks/useConfigurations', () => ({
  useConfigurations: () => ({
    data: {
      results: [
        {
          id: 1,
          name: 'Test Config 1',
          strategy_type: 'MA_CROSSOVER',
          description: 'Test configuration 1',
        },
        {
          id: 2,
          name: 'Test Config 2',
          strategy_type: 'RSI',
          description: 'Test configuration 2',
        },
      ],
    },
    isLoading: false,
  }),
  useConfiguration: (id: number) => ({
    data:
      id === 1
        ? {
            id: 1,
            name: 'Test Config 1',
            strategy_type: 'MA_CROSSOVER',
            description: 'Test configuration 1',
          }
        : id === 2
          ? {
              id: 2,
              name: 'Test Config 2',
              strategy_type: 'RSI',
              description: 'Test configuration 2',
            }
          : undefined,
    isLoading: false,
  }),
}));

// Mock i18next
vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

describe('BacktestTaskForm - Form State Persistence', () => {
  let queryClient: QueryClient;

  const renderForm = (
    props: Record<string, unknown> = {},
    withDefaultDates = true
  ) => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });

    // Provide default dates to avoid validation issues with date pickers
    const finalProps: Record<string, unknown> = { ...props };

    if (withDefaultDates) {
      finalProps.initialData = {
        start_time: '2024-01-01',
        end_time: '2024-12-31',
        ...(props.initialData || {}),
      };
    }

    return render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <BacktestTaskForm {...finalProps} />
        </BrowserRouter>
      </QueryClientProvider>
    );
  };

  beforeEach(() => {
    mockNavigate.mockClear();
    mockCreateMutate.mockClear();
    mockUpdateMutate.mockClear();
    vi.clearAllMocks();
  });

  describe('Forward Navigation (Step 1 → Step 2 → Step 3)', () => {
    it('should persist config_id and name when navigating from step 1 to step 2', async () => {
      renderForm({}, false);

      // Verify we're on step 1
      expect(screen.getByText('Select Configuration')).toBeInTheDocument();

      // Fill step 1 fields
      const configSelect = screen
        .getByText('Select Configuration')
        .closest('div')
        ?.querySelector('[role="combobox"]');
      expect(configSelect).toBeInTheDocument();
      fireEvent.mouseDown(configSelect!);

      const config1Option = await screen.findByText('Test Config 1');
      fireEvent.click(config1Option);

      const nameInput = screen.getByLabelText(/Task Name/i);
      fireEvent.change(nameInput, { target: { value: 'My Test Task' } });

      // Navigate to step 2
      const nextButton = screen.getByRole('button', { name: /Next/i });
      fireEvent.click(nextButton);

      // Wait for step 2 to appear
      await waitFor(() => {
        expect(screen.getByText('Backtest Parameters')).toBeInTheDocument();
      });

      // Navigate back to step 1
      const backButton = screen.getByRole('button', { name: /Back/i });
      fireEvent.click(backButton);

      // Verify step 1 values are still present
      await waitFor(() => {
        expect(screen.getByText('Select Configuration')).toBeInTheDocument();
      });

      const nameInputAfterBack = screen.getByLabelText(
        /Task Name/i
      ) as HTMLInputElement;
      expect(nameInputAfterBack.value).toBe('My Test Task');
    }, 15000);

    it('should persist all step 2 parameters when navigating to step 3', async () => {
      renderForm();

      // Fill step 1
      const configSelect = screen
        .getByText('Select Configuration')
        .closest('div')
        ?.querySelector('[role="combobox"]');
      fireEvent.mouseDown(configSelect!);
      const config1Option = await screen.findByText('Test Config 1');
      fireEvent.click(config1Option);

      const nameInput = screen.getByLabelText(/Task Name/i);
      fireEvent.change(nameInput, { target: { value: 'Test Task' } });

      // Navigate to step 2
      fireEvent.click(screen.getByRole('button', { name: /Next/i }));

      await waitFor(() => {
        expect(screen.getByText('Backtest Parameters')).toBeInTheDocument();
      });

      // Fill step 2 fields
      // Date fields are pre-filled via initialData

      // Select data source
      const postgresqlRadio = screen.getByRole('radio', {
        name: /PostgreSQL/i,
      });
      fireEvent.click(postgresqlRadio);

      const balanceInput = screen.getByLabelText(/Initial Balance/i);
      fireEvent.change(balanceInput, { target: { value: '50000' } });

      // Select instrument
      const instrumentSelect = screen.getByLabelText(/Instrument/i);
      fireEvent.mouseDown(instrumentSelect);
      const instrumentOption = await screen.findByText('USD_JPY');
      fireEvent.click(instrumentOption);

      // Navigate to step 3
      fireEvent.click(screen.getByRole('button', { name: /Next/i }));

      await waitFor(() => {
        expect(screen.getByText('Review & Submit')).toBeInTheDocument();
      });

      // Verify all values are displayed in review
      expect(screen.getByText('Test Task')).toBeInTheDocument();
      expect(screen.getByText('Test Config 1')).toBeInTheDocument();
    }, 15000);

    it('should maintain validation state when navigating forward', async () => {
      renderForm({}, false);

      // Try to navigate without filling required fields
      const nextButton = screen.getByRole('button', { name: /Next/i });
      fireEvent.click(nextButton);

      // Should stay on step 1 due to validation
      await waitFor(() => {
        expect(screen.getByText('Select Configuration')).toBeInTheDocument();
      });

      // Fill required fields
      const configSelect = screen
        .getByText('Select Configuration')
        .closest('div')
        ?.querySelector('[role="combobox"]');
      fireEvent.mouseDown(configSelect!);
      const config1Option = await screen.findByText('Test Config 1');
      fireEvent.click(config1Option);

      const nameInput = screen.getByLabelText(/Task Name/i);
      fireEvent.change(nameInput, { target: { value: 'Valid Task' } });

      // Now navigation should work
      fireEvent.click(nextButton);

      await waitFor(() => {
        expect(screen.getByText('Backtest Parameters')).toBeInTheDocument();
      });
    });
  });

  describe('Backward Navigation (Step 3 → Step 2 → Step 1)', () => {
    it('should persist all values when navigating backward from step 3 to step 1', async () => {
      renderForm();

      // Fill step 1
      const configSelect = screen
        .getByText('Select Configuration')
        .closest('div')
        ?.querySelector('[role="combobox"]');
      fireEvent.mouseDown(configSelect!);
      const config2Option = await screen.findByText('Test Config 2');
      fireEvent.click(config2Option);

      const nameInput = screen.getByLabelText(/Task Name/i);
      fireEvent.change(nameInput, { target: { value: 'Backward Test' } });

      const descriptionInput = screen.getByLabelText(/Description/i);
      fireEvent.change(descriptionInput, {
        target: { value: 'Testing backward navigation' },
      });

      // Navigate to step 2
      fireEvent.click(screen.getByRole('button', { name: /Next/i }));

      await waitFor(() => {
        expect(screen.getByText('Backtest Parameters')).toBeInTheDocument();
      });

      // Fill step 2
      // Date fields are pre-filled via initialData

      // Select data source
      const postgresqlRadio = screen.getByRole('radio', {
        name: /PostgreSQL/i,
      });
      fireEvent.click(postgresqlRadio);

      const balanceInput = screen.getByLabelText(/Initial Balance/i);
      fireEvent.change(balanceInput, { target: { value: '25000' } });

      // Select instrument
      const instrumentSelect = screen.getByLabelText(/Instrument/i);
      fireEvent.mouseDown(instrumentSelect);
      const instrumentOption = await screen.findByText('USD_JPY');
      fireEvent.click(instrumentOption);

      // Navigate to step 3
      fireEvent.click(screen.getByRole('button', { name: /Next/i }));

      await waitFor(() => {
        expect(screen.getByText('Review & Submit')).toBeInTheDocument();
      });

      // Navigate back to step 2
      fireEvent.click(screen.getByRole('button', { name: /Back/i }));

      await waitFor(() => {
        expect(screen.getByText('Backtest Parameters')).toBeInTheDocument();
      });

      // Verify step 2 values persist
      const balanceInputAfterBack = screen.getByLabelText(
        /Initial Balance/i
      ) as HTMLInputElement;
      expect(balanceInputAfterBack.value).toBe('25000');

      // Navigate back to step 1
      fireEvent.click(screen.getByRole('button', { name: /Back/i }));

      await waitFor(() => {
        expect(screen.getByText('Select Configuration')).toBeInTheDocument();
      });

      // Verify step 1 values persist
      const nameInputAfterBack = screen.getByLabelText(
        /Task Name/i
      ) as HTMLInputElement;
      expect(nameInputAfterBack.value).toBe('Backward Test');

      const descriptionInputAfterBack = screen.getByLabelText(
        /Description/i
      ) as HTMLInputElement;
      expect(descriptionInputAfterBack.value).toBe(
        'Testing backward navigation'
      );
    }, 15000);
  });

  describe('Mixed Navigation (Forward and Backward Multiple Times)', () => {
    it('should maintain form state through multiple forward and backward navigations', async () => {
      renderForm();

      // Step 1: Fill initial values
      const configSelect = screen
        .getByText('Select Configuration')
        .closest('div')
        ?.querySelector('[role="combobox"]');
      fireEvent.mouseDown(configSelect!);
      const config1Option = await screen.findByText('Test Config 1');
      fireEvent.click(config1Option);

      const nameInput = screen.getByLabelText(/Task Name/i);
      fireEvent.change(nameInput, { target: { value: 'Mixed Nav Test' } });

      // Forward to step 2
      fireEvent.click(screen.getByRole('button', { name: /Next/i }));

      await waitFor(() => {
        expect(screen.getByText('Backtest Parameters')).toBeInTheDocument();
      });

      // Fill step 2
      // Select data source
      const postgresqlRadio = screen.getByRole('radio', {
        name: /PostgreSQL/i,
      });
      fireEvent.click(postgresqlRadio);

      const balanceInput = screen.getByLabelText(/Initial Balance/i);
      fireEvent.change(balanceInput, { target: { value: '30000' } });

      // Select instrument
      const instrumentSelect = screen.getByLabelText(/Instrument/i);
      fireEvent.mouseDown(instrumentSelect);
      const instrumentOption = await screen.findByText('USD_JPY');
      fireEvent.click(instrumentOption);

      // Back to step 1
      fireEvent.click(screen.getByRole('button', { name: /Back/i }));

      await waitFor(() => {
        expect(screen.getByText('Select Configuration')).toBeInTheDocument();
      });

      // Verify step 1 values
      const nameInputCheck1 = screen.getByLabelText(
        /Task Name/i
      ) as HTMLInputElement;
      expect(nameInputCheck1.value).toBe('Mixed Nav Test');

      // Forward to step 2 again
      fireEvent.click(screen.getByRole('button', { name: /Next/i }));

      await waitFor(() => {
        expect(screen.getByText('Backtest Parameters')).toBeInTheDocument();
      });

      // Verify step 2 values persisted
      const balanceInputCheck = screen.getByLabelText(
        /Initial Balance/i
      ) as HTMLInputElement;
      expect(balanceInputCheck.value).toBe('30000');

      // Modify step 2 value
      const commissionInput = screen.getByLabelText(/Commission Per Trade/i);
      fireEvent.change(commissionInput, { target: { value: '5' } });

      // Forward to step 3
      fireEvent.click(screen.getByRole('button', { name: /Next/i }));

      await waitFor(() => {
        expect(screen.getByText('Review & Submit')).toBeInTheDocument();
      });

      // Back to step 2
      fireEvent.click(screen.getByRole('button', { name: /Back/i }));

      await waitFor(() => {
        expect(screen.getByText('Backtest Parameters')).toBeInTheDocument();
      });

      // Verify modified value persisted
      const commissionInputCheck = screen.getByLabelText(
        /Commission Per Trade/i
      ) as HTMLInputElement;
      expect(commissionInputCheck.value).toBe('5');

      // Back to step 1
      fireEvent.click(screen.getByRole('button', { name: /Back/i }));

      await waitFor(() => {
        expect(screen.getByText('Select Configuration')).toBeInTheDocument();
      });

      // Verify step 1 still has original values
      const nameInputCheck2 = screen.getByLabelText(
        /Task Name/i
      ) as HTMLInputElement;
      expect(nameInputCheck2.value).toBe('Mixed Nav Test');

      // Forward through all steps to review
      fireEvent.click(screen.getByRole('button', { name: /Next/i }));

      await waitFor(() => {
        expect(screen.getByText('Backtest Parameters')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByRole('button', { name: /Next/i }));

      await waitFor(() => {
        expect(screen.getByText('Review & Submit')).toBeInTheDocument();
      });

      // Verify all values are present in review
      expect(screen.getByText('Mixed Nav Test')).toBeInTheDocument();
      expect(screen.getByText('Test Config 1')).toBeInTheDocument();
    }, 15000);

    it('should handle field modifications during mixed navigation', async () => {
      renderForm();

      // Fill step 1
      const configSelect = screen
        .getByText('Select Configuration')
        .closest('div')
        ?.querySelector('[role="combobox"]');
      fireEvent.mouseDown(configSelect!);
      const config1Option = await screen.findByText('Test Config 1');
      fireEvent.click(config1Option);

      const nameInput = screen.getByLabelText(/Task Name/i);
      fireEvent.change(nameInput, { target: { value: 'Original Name' } });

      // Forward to step 2
      fireEvent.click(screen.getByRole('button', { name: /Next/i }));

      await waitFor(() => {
        expect(screen.getByText('Backtest Parameters')).toBeInTheDocument();
      });

      // Back to step 1
      fireEvent.click(screen.getByRole('button', { name: /Back/i }));

      await waitFor(() => {
        expect(screen.getByText('Select Configuration')).toBeInTheDocument();
      });

      // Modify step 1 value
      const nameInputModify = screen.getByLabelText(/Task Name/i);
      fireEvent.change(nameInputModify, { target: { value: 'Modified Name' } });

      // Forward to step 2
      fireEvent.click(screen.getByRole('button', { name: /Next/i }));

      await waitFor(() => {
        expect(screen.getByText('Backtest Parameters')).toBeInTheDocument();
      });

      // Fill step 2
      // Select data source
      const postgresqlRadio = screen.getByRole('radio', {
        name: /PostgreSQL/i,
      });
      fireEvent.click(postgresqlRadio);

      const balanceInput = screen.getByLabelText(/Initial Balance/i);
      fireEvent.change(balanceInput, { target: { value: '40000' } });

      // Select instrument
      const instrumentSelect = screen.getByLabelText(/Instrument/i);
      fireEvent.mouseDown(instrumentSelect);
      const instrumentOption = await screen.findByText('USD_JPY');
      fireEvent.click(instrumentOption);

      // Forward to step 3
      fireEvent.click(screen.getByRole('button', { name: /Next/i }));

      await waitFor(() => {
        expect(screen.getByText('Review & Submit')).toBeInTheDocument();
      });

      // Verify modified name is shown
      expect(screen.getByText('Modified Name')).toBeInTheDocument();
    });
  });

  describe('Validation State Persistence', () => {
    it('should maintain validation errors when navigating back and forth', async () => {
      renderForm({}, false);

      // Try to proceed without filling required fields
      fireEvent.click(screen.getByRole('button', { name: /Next/i }));

      // Should stay on step 1
      await waitFor(() => {
        expect(screen.getByText('Select Configuration')).toBeInTheDocument();
      });

      // Fill only name (missing config_id)
      const nameInput = screen.getByLabelText(/Task Name/i);
      fireEvent.change(nameInput, { target: { value: 'Test' } });

      // Try to proceed again
      fireEvent.click(screen.getByRole('button', { name: /Next/i }));

      // Should still stay on step 1 due to missing config_id
      await waitFor(() => {
        expect(screen.getByText('Select Configuration')).toBeInTheDocument();
      });

      // Now fill config_id
      const configSelect = screen
        .getByText('Select Configuration')
        .closest('div')
        ?.querySelector('[role="combobox"]');
      fireEvent.mouseDown(configSelect!);
      const config1Option = await screen.findByText('Test Config 1');
      fireEvent.click(config1Option);

      // Now should be able to proceed
      fireEvent.click(screen.getByRole('button', { name: /Next/i }));

      await waitFor(() => {
        expect(screen.getByText('Backtest Parameters')).toBeInTheDocument();
      });
    });

    it('should clear validation errors when fields are corrected', async () => {
      renderForm();

      // Fill step 1 with valid data
      const configSelect = screen
        .getByText('Select Configuration')
        .closest('div')
        ?.querySelector('[role="combobox"]');
      fireEvent.mouseDown(configSelect!);
      const config1Option = await screen.findByText('Test Config 1');
      fireEvent.click(config1Option);

      const nameInput = screen.getByLabelText(/Task Name/i);
      fireEvent.change(nameInput, { target: { value: 'Valid Task' } });

      // Navigate to step 2
      fireEvent.click(screen.getByRole('button', { name: /Next/i }));

      await waitFor(() => {
        expect(screen.getByText('Backtest Parameters')).toBeInTheDocument();
      });

      // Try to navigate to step 3 without filling required fields
      fireEvent.click(screen.getByRole('button', { name: /Next/i }));

      // Should stay on step 2
      await waitFor(() => {
        expect(screen.getByText('Backtest Parameters')).toBeInTheDocument();
      });

      // Fill required fields
      // Date fields are pre-filled via initialData

      // Select data source (it's a radio button, not a select)
      const postgresqlRadio = screen.getByRole('radio', {
        name: /PostgreSQL/i,
      });
      fireEvent.click(postgresqlRadio);

      const balanceInput = screen.getByLabelText(/Initial Balance/i);
      fireEvent.change(balanceInput, { target: { value: '10000' } });

      // Select instrument using the select element directly
      const instrumentSelect = screen.getByLabelText(/Instrument/i);
      fireEvent.mouseDown(instrumentSelect);
      const instrumentOption = await screen.findByText('USD_JPY');
      fireEvent.click(instrumentOption);

      // Now should be able to proceed
      fireEvent.click(screen.getByRole('button', { name: /Next/i }));

      await waitFor(() => {
        expect(screen.getByText('Review & Submit')).toBeInTheDocument();
      });
    });
  });

  describe('Edit Mode with initialData', () => {
    it('should populate form with initialData and maintain values through navigation', async () => {
      const initialData = {
        config_id: 1,
        name: 'Existing Task',
        description: 'Existing description',
        data_source: DataSource.POSTGRESQL,
        start_time: '2024-01-01',
        end_time: '2024-12-31',
        initial_balance: 15000,
        commission_per_trade: 2,
        instrument: 'EUR_USD',
      };

      renderForm({ taskId: 123, initialData });

      // Verify step 1 is populated
      const nameInput = screen.getByLabelText(/Task Name/i) as HTMLInputElement;
      expect(nameInput.value).toBe('Existing Task');

      const descriptionInput = screen.getByLabelText(
        /Description/i
      ) as HTMLInputElement;
      expect(descriptionInput.value).toBe('Existing description');

      // Navigate to step 2
      fireEvent.click(screen.getByRole('button', { name: /Next/i }));

      await waitFor(() => {
        expect(screen.getByText('Backtest Parameters')).toBeInTheDocument();
      });

      // Verify step 2 is populated
      const balanceInput = screen.getByLabelText(
        /Initial Balance/i
      ) as HTMLInputElement;
      expect(balanceInput.value).toBe('15000');

      // Navigate back to step 1
      fireEvent.click(screen.getByRole('button', { name: /Back/i }));

      await waitFor(() => {
        expect(screen.getByText('Select Configuration')).toBeInTheDocument();
      });

      // Verify values still present
      const nameInputCheck = screen.getByLabelText(
        /Task Name/i
      ) as HTMLInputElement;
      expect(nameInputCheck.value).toBe('Existing Task');

      // Navigate forward to step 3
      fireEvent.click(screen.getByRole('button', { name: /Next/i }));

      await waitFor(() => {
        expect(screen.getByText('Backtest Parameters')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByRole('button', { name: /Next/i }));

      await waitFor(() => {
        expect(screen.getByText('Review & Submit')).toBeInTheDocument();
      });

      // Verify submit button shows "Update Task"
      expect(
        screen.getByRole('button', { name: /Update Task/i })
      ).toBeInTheDocument();

      // Verify all values are displayed
      expect(screen.getByText('Existing Task')).toBeInTheDocument();
    });

    it('should call update API with correct data when submitting in edit mode', async () => {
      mockUpdateMutate.mockResolvedValue({});

      const initialData = {
        config_id: 2,
        name: 'Task to Update',
        description: 'Original description',
        data_source: DataSource.POSTGRESQL,
        start_time: '2024-03-01',
        end_time: '2024-03-31',
        initial_balance: 20000,
        commission_per_trade: 3,
        instrument: 'GBP_USD',
      };

      renderForm({ taskId: 456, initialData });

      // Navigate through all steps to review
      fireEvent.click(screen.getByRole('button', { name: /Next/i }));

      await waitFor(() => {
        expect(screen.getByText('Backtest Parameters')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByRole('button', { name: /Next/i }));

      await waitFor(() => {
        expect(screen.getByText('Review & Submit')).toBeInTheDocument();
      });

      // Submit the form
      const updateButton = screen.getByRole('button', { name: /Update Task/i });
      fireEvent.click(updateButton);

      // Verify update API was called with correct parameters
      await waitFor(() => {
        expect(mockUpdateMutate).toHaveBeenCalledWith({
          id: 456,
          data: expect.objectContaining({
            config_id: 2,
            name: 'Task to Update',
            description: 'Original description',
            data_source: DataSource.POSTGRESQL,
            start_time: '2024-03-01',
            end_time: '2024-03-31',
            initial_balance: 20000,
            commission_per_trade: 3,
            instrument: 'GBP_USD',
          }),
        });
      });
    });

    it('should navigate to backtest tasks list after successful update', async () => {
      mockUpdateMutate.mockImplementation(async () => {
        return Promise.resolve({});
      });

      const initialData = {
        config_id: 1,
        name: 'Task for Navigation Test',
        description: 'Testing navigation after update',
        data_source: DataSource.POSTGRESQL,
        start_time: '2024-05-01',
        end_time: '2024-05-31',
        initial_balance: 12000,
        commission_per_trade: 1.5,
        instrument: 'AUD_USD',
      };

      renderForm({ taskId: 789, initialData });

      // Navigate to review step
      fireEvent.click(screen.getByRole('button', { name: /Next/i }));

      await waitFor(() => {
        expect(screen.getByText('Backtest Parameters')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByRole('button', { name: /Next/i }));

      await waitFor(() => {
        expect(screen.getByText('Review & Submit')).toBeInTheDocument();
      });

      // Submit the form
      const updateButton = screen.getByRole('button', { name: /Update Task/i });
      fireEvent.click(updateButton);

      // Verify navigation to backtest tasks list
      await waitFor(() => {
        expect(mockNavigate).toHaveBeenCalledWith('/backtest-tasks');
      });
    });

    it('should allow modifying initialData values before update', async () => {
      mockUpdateMutate.mockResolvedValue({});

      const initialData = {
        config_id: 1,
        name: 'Original Name',
        description: 'Original description',
        data_source: DataSource.POSTGRESQL,
        start_time: '2024-01-01',
        end_time: '2024-12-31',
        initial_balance: 10000,
        commission_per_trade: 0,
        instrument: 'USD_JPY',
      };

      renderForm({ taskId: 999, initialData });

      // Modify name in step 1
      const nameInput = screen.getByLabelText(/Task Name/i);
      fireEvent.change(nameInput, { target: { value: 'Modified Name' } });

      // Navigate to step 2
      fireEvent.click(screen.getByRole('button', { name: /Next/i }));

      await waitFor(() => {
        expect(screen.getByText('Backtest Parameters')).toBeInTheDocument();
      });

      // Modify balance in step 2
      const balanceInput = screen.getByLabelText(/Initial Balance/i);
      fireEvent.change(balanceInput, { target: { value: '25000' } });

      // Navigate to review
      fireEvent.click(screen.getByRole('button', { name: /Next/i }));

      await waitFor(() => {
        expect(screen.getByText('Review & Submit')).toBeInTheDocument();
      });

      // Verify modified values are shown in review
      expect(screen.getByText('Modified Name')).toBeInTheDocument();

      // Submit the form
      const updateButton = screen.getByRole('button', { name: /Update Task/i });
      fireEvent.click(updateButton);

      // Verify update API was called with modified values
      await waitFor(() => {
        expect(mockUpdateMutate).toHaveBeenCalledWith({
          id: 999,
          data: expect.objectContaining({
            name: 'Modified Name',
            initial_balance: 25000,
          }),
        });
      });
    });
  });

  describe('sell_at_completion checkbox', () => {
    it('should render the sell_at_completion checkbox in step 2', async () => {
      renderForm();

      // Navigate to step 2
      const configSelect = screen
        .getByText('Select Configuration')
        .closest('div')
        ?.querySelector('[role="combobox"]');
      fireEvent.mouseDown(configSelect!);
      const config1Option = await screen.findByText('Test Config 1');
      fireEvent.click(config1Option);

      const nameInput = screen.getByLabelText(/Task Name/i);
      fireEvent.change(nameInput, { target: { value: 'Test Task' } });

      fireEvent.click(screen.getByRole('button', { name: /Next/i }));

      await waitFor(() => {
        expect(screen.getByText('Backtest Parameters')).toBeInTheDocument();
      });

      // Verify checkbox is rendered
      const checkbox = screen.getByRole('checkbox', {
        name: /Close all positions at backtest completion/i,
      });
      expect(checkbox).toBeInTheDocument();
    });

    it('should have default value of false for sell_at_completion', async () => {
      renderForm();

      // Navigate to step 2
      const configSelect = screen
        .getByText('Select Configuration')
        .closest('div')
        ?.querySelector('[role="combobox"]');
      fireEvent.mouseDown(configSelect!);
      const config1Option = await screen.findByText('Test Config 1');
      fireEvent.click(config1Option);

      const nameInput = screen.getByLabelText(/Task Name/i);
      fireEvent.change(nameInput, { target: { value: 'Test Task' } });

      fireEvent.click(screen.getByRole('button', { name: /Next/i }));

      await waitFor(() => {
        expect(screen.getByText('Backtest Parameters')).toBeInTheDocument();
      });

      // Verify checkbox is unchecked by default
      const checkbox = screen.getByRole('checkbox', {
        name: /Close all positions at backtest completion/i,
      }) as HTMLInputElement;
      expect(checkbox.checked).toBe(false);
    });

    it('should update form state when checkbox is toggled', async () => {
      renderForm();

      // Navigate to step 2
      const configSelect = screen
        .getByText('Select Configuration')
        .closest('div')
        ?.querySelector('[role="combobox"]');
      fireEvent.mouseDown(configSelect!);
      const config1Option = await screen.findByText('Test Config 1');
      fireEvent.click(config1Option);

      const nameInput = screen.getByLabelText(/Task Name/i);
      fireEvent.change(nameInput, { target: { value: 'Test Task' } });

      fireEvent.click(screen.getByRole('button', { name: /Next/i }));

      await waitFor(() => {
        expect(screen.getByText('Backtest Parameters')).toBeInTheDocument();
      });

      // Toggle checkbox
      const checkbox = screen.getByRole('checkbox', {
        name: /Close all positions at backtest completion/i,
      }) as HTMLInputElement;
      fireEvent.click(checkbox);

      // Verify checkbox is now checked
      expect(checkbox.checked).toBe(true);

      // Toggle back
      fireEvent.click(checkbox);
      expect(checkbox.checked).toBe(false);
    });

    it('should include sell_at_completion in form submission', async () => {
      mockCreateMutate.mockResolvedValue({});

      renderForm();

      // Fill step 1
      const configSelect = screen
        .getByText('Select Configuration')
        .closest('div')
        ?.querySelector('[role="combobox"]');
      fireEvent.mouseDown(configSelect!);
      const config1Option = await screen.findByText('Test Config 1');
      fireEvent.click(config1Option);

      const nameInput = screen.getByLabelText(/Task Name/i);
      fireEvent.change(nameInput, { target: { value: 'Test Task' } });

      fireEvent.click(screen.getByRole('button', { name: /Next/i }));

      await waitFor(() => {
        expect(screen.getByText('Backtest Parameters')).toBeInTheDocument();
      });

      // Fill step 2 and check the checkbox
      const postgresqlRadio = screen.getByRole('radio', {
        name: /PostgreSQL/i,
      });
      fireEvent.click(postgresqlRadio);

      const balanceInput = screen.getByLabelText(/Initial Balance/i);
      fireEvent.change(balanceInput, { target: { value: '10000' } });

      const instrumentSelect = screen.getByLabelText(/Instrument/i);
      fireEvent.mouseDown(instrumentSelect);
      const instrumentOption = await screen.findByText('USD_JPY');
      fireEvent.click(instrumentOption);

      const checkbox = screen.getByRole('checkbox', {
        name: /Close all positions at backtest completion/i,
      });
      fireEvent.click(checkbox);

      // Navigate to review
      fireEvent.click(screen.getByRole('button', { name: /Next/i }));

      await waitFor(() => {
        expect(screen.getByText('Review & Submit')).toBeInTheDocument();
      });

      // Submit the form
      const createButton = screen.getByRole('button', {
        name: /Create Task/i,
      });
      fireEvent.click(createButton);

      // Verify API was called with sell_at_completion: true
      await waitFor(() => {
        expect(mockCreateMutate).toHaveBeenCalledWith(
          expect.objectContaining({
            sell_at_completion: true,
          })
        );
      });
    });

    it('should display sell_at_completion value in review step', async () => {
      renderForm();

      // Fill step 1
      const configSelect = screen
        .getByText('Select Configuration')
        .closest('div')
        ?.querySelector('[role="combobox"]');
      fireEvent.mouseDown(configSelect!);
      const config1Option = await screen.findByText('Test Config 1');
      fireEvent.click(config1Option);

      const nameInput = screen.getByLabelText(/Task Name/i);
      fireEvent.change(nameInput, { target: { value: 'Test Task' } });

      fireEvent.click(screen.getByRole('button', { name: /Next/i }));

      await waitFor(() => {
        expect(screen.getByText('Backtest Parameters')).toBeInTheDocument();
      });

      // Fill step 2 and check the checkbox
      const postgresqlRadio = screen.getByRole('radio', {
        name: /PostgreSQL/i,
      });
      fireEvent.click(postgresqlRadio);

      const balanceInput = screen.getByLabelText(/Initial Balance/i);
      fireEvent.change(balanceInput, { target: { value: '10000' } });

      const instrumentSelect = screen.getByLabelText(/Instrument/i);
      fireEvent.mouseDown(instrumentSelect);
      const instrumentOption = await screen.findByText('USD_JPY');
      fireEvent.click(instrumentOption);

      const checkbox = screen.getByRole('checkbox', {
        name: /Close all positions at backtest completion/i,
      });
      fireEvent.click(checkbox);

      // Navigate to review
      fireEvent.click(screen.getByRole('button', { name: /Next/i }));

      await waitFor(() => {
        expect(screen.getByText('Review & Submit')).toBeInTheDocument();
      });

      // Verify the value is displayed in review
      expect(
        screen.getByText('Close Positions at Completion')
      ).toBeInTheDocument();
      // Find the "Yes" text that appears after the label
      const reviewSection = screen.getByText(
        'Close Positions at Completion'
      ).parentElement;
      expect(reviewSection).toHaveTextContent('Yes');
    });

    it('should persist sell_at_completion value when navigating back and forth', async () => {
      renderForm();

      // Fill step 1
      const configSelect = screen
        .getByText('Select Configuration')
        .closest('div')
        ?.querySelector('[role="combobox"]');
      fireEvent.mouseDown(configSelect!);
      const config1Option = await screen.findByText('Test Config 1');
      fireEvent.click(config1Option);

      const nameInput = screen.getByLabelText(/Task Name/i);
      fireEvent.change(nameInput, { target: { value: 'Test Task' } });

      fireEvent.click(screen.getByRole('button', { name: /Next/i }));

      await waitFor(() => {
        expect(screen.getByText('Backtest Parameters')).toBeInTheDocument();
      });

      // Check the checkbox
      const checkbox = screen.getByRole('checkbox', {
        name: /Close all positions at backtest completion/i,
      }) as HTMLInputElement;
      fireEvent.click(checkbox);
      expect(checkbox.checked).toBe(true);

      // Navigate to review
      const postgresqlRadio = screen.getByRole('radio', {
        name: /PostgreSQL/i,
      });
      fireEvent.click(postgresqlRadio);

      const balanceInput = screen.getByLabelText(/Initial Balance/i);
      fireEvent.change(balanceInput, { target: { value: '10000' } });

      const instrumentSelect = screen.getByLabelText(/Instrument/i);
      fireEvent.mouseDown(instrumentSelect);
      const instrumentOption = await screen.findByText('USD_JPY');
      fireEvent.click(instrumentOption);

      fireEvent.click(screen.getByRole('button', { name: /Next/i }));

      await waitFor(() => {
        expect(screen.getByText('Review & Submit')).toBeInTheDocument();
      });

      // Navigate back to step 2
      fireEvent.click(screen.getByRole('button', { name: /Back/i }));

      await waitFor(() => {
        expect(screen.getByText('Backtest Parameters')).toBeInTheDocument();
      });

      // Verify checkbox is still checked
      const checkboxAfterBack = screen.getByRole('checkbox', {
        name: /Close all positions at backtest completion/i,
      }) as HTMLInputElement;
      expect(checkboxAfterBack.checked).toBe(true);
    });
  });
});
