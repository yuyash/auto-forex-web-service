import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import TradingTaskForm from '../components/trading/TradingTaskForm';

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
vi.mock('../hooks/useTradingTaskMutations', () => ({
  useCreateTradingTask: () => ({
    mutate: mockCreateMutate,
    isLoading: false,
  }),
  useUpdateTradingTask: () => ({
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

vi.mock('../hooks/useAccounts', () => ({
  useAccounts: () => ({
    data: {
      results: [
        {
          id: 1,
          account_id: '001-001-1234567-001',
          api_type: 'practice',
          balance: '10000.00',
          currency: 'USD',
        },
        {
          id: 2,
          account_id: '001-001-7654321-001',
          api_type: 'live',
          balance: '50000.00',
          currency: 'USD',
        },
      ],
    },
    isLoading: false,
  }),
}));

vi.mock('../hooks/useTradingTasks', () => ({
  useTradingTasks: () => ({
    data: {
      results: [],
    },
    isLoading: false,
  }),
}));

vi.mock('../hooks/useStrategies', () => ({
  useStrategies: () => ({
    strategies: [
      { value: 'MA_CROSSOVER', label: 'MA Crossover' },
      { value: 'RSI', label: 'RSI Strategy' },
    ],
  }),
  getStrategyDisplayName: (strategies: unknown[], type: string) => {
    const strategy = (
      strategies as Array<{ value: string; label: string }>
    ).find((s) => s.value === type);
    return strategy?.label || type;
  },
}));

describe('TradingTaskForm - sell_on_stop checkbox', () => {
  let queryClient: QueryClient;

  const renderForm = (props: Record<string, unknown> = {}) => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });

    return render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <TradingTaskForm {...props} />
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

  it('should render the sell_on_stop checkbox in step 2 (Configuration)', async () => {
    renderForm();

    // Navigate to step 1 (Configuration)
    const accountSelect = screen
      .getByText('Select Trading Account')
      .closest('div')
      ?.parentElement?.querySelector('[role="combobox"]');
    expect(accountSelect).toBeInTheDocument();
    fireEvent.mouseDown(accountSelect!);

    const account1Option = await screen.findByText(/001-001-1234567-001/);
    fireEvent.click(account1Option);

    fireEvent.click(screen.getByRole('button', { name: /Next/i }));

    await waitFor(() => {
      expect(screen.getByText('Select Configuration')).toBeInTheDocument();
    });

    // Verify checkbox is rendered
    const checkbox = screen.getByRole('checkbox', {
      name: /Close all positions when task is stopped/i,
    });
    expect(checkbox).toBeInTheDocument();
  });

  it('should have default value of false for sell_on_stop', async () => {
    renderForm();

    // Navigate to step 1 (Configuration)
    const accountSelect = screen
      .getByText('Select Trading Account')
      .closest('div')
      ?.parentElement?.querySelector('[role="combobox"]');
    fireEvent.mouseDown(accountSelect!);

    const account1Option = await screen.findByText(/001-001-1234567-001/);
    fireEvent.click(account1Option);

    fireEvent.click(screen.getByRole('button', { name: /Next/i }));

    await waitFor(() => {
      expect(screen.getByText('Select Configuration')).toBeInTheDocument();
    });

    // Verify checkbox is unchecked by default
    const checkbox = screen.getByRole('checkbox', {
      name: /Close all positions when task is stopped/i,
    }) as HTMLInputElement;
    expect(checkbox.checked).toBe(false);
  });

  it('should update form state when checkbox is toggled', async () => {
    renderForm();

    // Navigate to step 1 (Configuration)
    const accountSelect = screen
      .getByText('Select Trading Account')
      .closest('div')
      ?.parentElement?.querySelector('[role="combobox"]');
    fireEvent.mouseDown(accountSelect!);

    const account1Option = await screen.findByText(/001-001-1234567-001/);
    fireEvent.click(account1Option);

    fireEvent.click(screen.getByRole('button', { name: /Next/i }));

    await waitFor(() => {
      expect(screen.getByText('Select Configuration')).toBeInTheDocument();
    });

    // Toggle checkbox
    const checkbox = screen.getByRole('checkbox', {
      name: /Close all positions when task is stopped/i,
    }) as HTMLInputElement;
    fireEvent.click(checkbox);

    // Verify checkbox is now checked
    expect(checkbox.checked).toBe(true);

    // Toggle back
    fireEvent.click(checkbox);
    expect(checkbox.checked).toBe(false);
  });

  it('should include sell_on_stop in form submission', async () => {
    mockCreateMutate.mockResolvedValue({});

    renderForm();

    // Fill step 0 (Account)
    const accountSelect = screen
      .getByText('Select Trading Account')
      .closest('div')
      ?.parentElement?.querySelector('[role="combobox"]');
    fireEvent.mouseDown(accountSelect!);

    const account1Option = await screen.findByText(/001-001-1234567-001/);
    fireEvent.click(account1Option);

    fireEvent.click(screen.getByRole('button', { name: /Next/i }));

    await waitFor(() => {
      expect(screen.getByText('Select Configuration')).toBeInTheDocument();
    });

    // Fill step 1 (Configuration) and check the checkbox
    const configSelect = screen
      .getByText('Select Configuration')
      .closest('div')
      ?.parentElement?.querySelector('[role="combobox"]');
    fireEvent.mouseDown(configSelect!);

    const config1Option = await screen.findByText('Test Config 1');
    fireEvent.click(config1Option);

    const nameInput = screen.getByLabelText(/Task Name/i);
    fireEvent.change(nameInput, { target: { value: 'Test Task' } });

    const checkbox = screen.getByRole('checkbox', {
      name: /Close all positions when task is stopped/i,
    });
    fireEvent.click(checkbox);

    // Navigate to review
    fireEvent.click(screen.getByRole('button', { name: /Next/i }));

    await waitFor(() => {
      expect(screen.getByText('Review and Confirm')).toBeInTheDocument();
    });

    // Submit the form
    const createButton = screen.getByRole('button', {
      name: /Create Task/i,
    });
    fireEvent.click(createButton);

    // Verify API was called with sell_on_stop: true
    await waitFor(() => {
      expect(mockCreateMutate).toHaveBeenCalledWith(
        expect.objectContaining({
          sell_on_stop: true,
        })
      );
    });
  });

  it('should display sell_on_stop value in review step', async () => {
    renderForm();

    // Fill step 0 (Account)
    const accountSelect = screen
      .getByText('Select Trading Account')
      .closest('div')
      ?.parentElement?.querySelector('[role="combobox"]');
    fireEvent.mouseDown(accountSelect!);

    const account1Option = await screen.findByText(/001-001-1234567-001/);
    fireEvent.click(account1Option);

    fireEvent.click(screen.getByRole('button', { name: /Next/i }));

    await waitFor(() => {
      expect(screen.getByText('Select Configuration')).toBeInTheDocument();
    });

    // Fill step 1 (Configuration) and check the checkbox
    const configSelect = screen
      .getByText('Select Configuration')
      .closest('div')
      ?.parentElement?.querySelector('[role="combobox"]');
    fireEvent.mouseDown(configSelect!);

    const config1Option = await screen.findByText('Test Config 1');
    fireEvent.click(config1Option);

    const nameInput = screen.getByLabelText(/Task Name/i);
    fireEvent.change(nameInput, { target: { value: 'Test Task' } });

    const checkbox = screen.getByRole('checkbox', {
      name: /Close all positions when task is stopped/i,
    });
    fireEvent.click(checkbox);

    // Navigate to review
    fireEvent.click(screen.getByRole('button', { name: /Next/i }));

    await waitFor(() => {
      expect(screen.getByText('Review and Confirm')).toBeInTheDocument();
    });

    // Verify the value is displayed in review
    expect(screen.getByText('Close Positions on Stop')).toBeInTheDocument();
    // Find the "Yes" text that appears after the label
    const reviewSection = screen.getByText(
      'Close Positions on Stop'
    ).parentElement;
    expect(reviewSection).toHaveTextContent('Yes');
  });

  it('should persist sell_on_stop value when navigating back and forth', async () => {
    renderForm();

    // Fill step 0 (Account)
    const accountSelect = screen
      .getByText('Select Trading Account')
      .closest('div')
      ?.parentElement?.querySelector('[role="combobox"]');
    fireEvent.mouseDown(accountSelect!);

    const account1Option = await screen.findByText(/001-001-1234567-001/);
    fireEvent.click(account1Option);

    fireEvent.click(screen.getByRole('button', { name: /Next/i }));

    await waitFor(() => {
      expect(screen.getByText('Select Configuration')).toBeInTheDocument();
    });

    // Check the checkbox
    const checkbox = screen.getByRole('checkbox', {
      name: /Close all positions when task is stopped/i,
    }) as HTMLInputElement;
    fireEvent.click(checkbox);
    expect(checkbox.checked).toBe(true);

    // Fill other required fields
    const configSelect = screen
      .getByText('Select Configuration')
      .closest('div')
      ?.parentElement?.querySelector('[role="combobox"]');
    fireEvent.mouseDown(configSelect!);

    const config1Option = await screen.findByText('Test Config 1');
    fireEvent.click(config1Option);

    const nameInput = screen.getByLabelText(/Task Name/i);
    fireEvent.change(nameInput, { target: { value: 'Test Task' } });

    // Navigate to review
    fireEvent.click(screen.getByRole('button', { name: /Next/i }));

    await waitFor(() => {
      expect(screen.getByText('Review and Confirm')).toBeInTheDocument();
    });

    // Navigate back to step 1
    fireEvent.click(screen.getByRole('button', { name: /Back/i }));

    await waitFor(() => {
      expect(screen.getByText('Select Configuration')).toBeInTheDocument();
    });

    // Verify checkbox is still checked
    const checkboxAfterBack = screen.getByRole('checkbox', {
      name: /Close all positions when task is stopped/i,
    }) as HTMLInputElement;
    expect(checkboxAfterBack.checked).toBe(true);
  });
});
