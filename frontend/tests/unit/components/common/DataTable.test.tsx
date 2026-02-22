/**
 * DataTable Unit Tests
 *
 * Tests for the enhanced DataTable component with loading and error states.
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import DataTable, { Column } from '../../../../src/components/common/DataTable';

interface TestData {
  id: number;
  name: string;
  value: number;
}

const mockColumns: Column<TestData>[] = [
  { id: 'id', label: 'ID', sortable: true },
  { id: 'name', label: 'Name', sortable: true, filterable: true },
  { id: 'value', label: 'Value', sortable: true },
];

const mockData: TestData[] = [
  { id: 1, name: 'Item 1', value: 100 },
  { id: 2, name: 'Item 2', value: 200 },
  { id: 3, name: 'Item 3', value: 300 },
];

describe('DataTable', () => {
  it('should render table with data', () => {
    render(<DataTable columns={mockColumns} data={mockData} />);

    expect(screen.getByText('Item 1')).toBeInTheDocument();
    expect(screen.getByText('Item 2')).toBeInTheDocument();
    expect(screen.getByText('Item 3')).toBeInTheDocument();
  });

  it('should render loading skeleton when isLoading is true and no data', () => {
    render(<DataTable columns={mockColumns} data={[]} isLoading={true} />);

    // Should render skeleton rows
    const skeletons = screen.getAllByRole('row');
    expect(skeletons.length).toBeGreaterThan(1); // Header + skeleton rows
  });

  it('should render error state when error is present', () => {
    const error = new Error('Failed to load data');
    render(<DataTable columns={mockColumns} data={[]} error={error} />);

    expect(screen.getByText(/Failed to load data/i)).toBeInTheDocument();
  });

  it('should render empty message when no data and not loading', () => {
    render(
      <DataTable
        columns={mockColumns}
        data={[]}
        emptyMessage="No items found"
      />
    );

    expect(screen.getByText('No items found')).toBeInTheDocument();
  });

  it('should sort data when column header is clicked', () => {
    render(<DataTable columns={mockColumns} data={mockData} />);

    const nameHeader = screen.getByText('Name');
    fireEvent.click(nameHeader);

    // After sorting, check order
    const rows = screen.getAllByRole('row');
    expect(rows[2]).toHaveTextContent('Item 1');
  });

  it('should filter data when filter input is changed', async () => {
    render(<DataTable columns={mockColumns} data={mockData} />);

    const filterInput = screen.getByPlaceholderText('Filter Name');
    fireEvent.change(filterInput, { target: { value: 'Item 2' } });

    await waitFor(() => {
      expect(screen.getByText('Item 2')).toBeInTheDocument();
      expect(screen.queryByText('Item 1')).not.toBeInTheDocument();
      expect(screen.queryByText('Item 3')).not.toBeInTheDocument();
    });
  });

  it('should paginate data', () => {
    const largeData = Array.from({ length: 25 }, (_, i) => ({
      id: i + 1,
      name: `Item ${i + 1}`,
      value: (i + 1) * 100,
    }));

    render(
      <DataTable
        columns={mockColumns}
        data={largeData}
        defaultRowsPerPage={10}
      />
    );

    // Should show first 10 items
    expect(screen.getByText('Item 1')).toBeInTheDocument();
    expect(screen.getByText('Item 10')).toBeInTheDocument();
    expect(screen.queryByText('Item 11')).not.toBeInTheDocument();

    // Click next page
    const nextButton = screen.getByRole('button', { name: /next page/i });
    fireEvent.click(nextButton);

    // Should show next 10 items
    expect(screen.queryByText('Item 1')).not.toBeInTheDocument();
    expect(screen.getByText('Item 11')).toBeInTheDocument();
    expect(screen.getByText('Item 20')).toBeInTheDocument();
  });

  it('should call onRowClick when row is clicked', () => {
    const handleRowClick = vi.fn();
    render(
      <DataTable
        columns={mockColumns}
        data={mockData}
        onRowClick={handleRowClick}
      />
    );

    const row = screen.getByText('Item 1').closest('tr');
    if (row) {
      fireEvent.click(row);
      expect(handleRowClick).toHaveBeenCalledWith(mockData[0]);
    }
  });

  it('should show updating indicator when loading with existing data', () => {
    render(
      <DataTable columns={mockColumns} data={mockData} isLoading={true} />
    );

    expect(screen.getByText('Updating...')).toBeInTheDocument();
    expect(screen.getByText('Item 1')).toBeInTheDocument(); // Data still visible
  });

  it('should support real-time updates when enabled', () => {
    vi.useFakeTimers();
    const handleRefresh = vi.fn();

    render(
      <DataTable
        columns={mockColumns}
        data={mockData}
        enableRealTimeUpdates={true}
        onRefresh={handleRefresh}
      />
    );

    // Fast-forward time by 5 seconds
    vi.advanceTimersByTime(5000);

    expect(handleRefresh).toHaveBeenCalled();

    vi.useRealTimers();
  });

  it('should render custom cell content with render function', () => {
    const columnsWithRender: Column<TestData>[] = [
      {
        id: 'name',
        label: 'Name',
        render: (row) => <strong>{row.name}</strong>,
      },
    ];

    render(<DataTable columns={columnsWithRender} data={mockData} />);

    const strongElement = screen.getByText('Item 1').closest('strong');
    expect(strongElement).toBeInTheDocument();
  });

  it('should have proper accessibility attributes', () => {
    render(
      <DataTable
        columns={mockColumns}
        data={mockData}
        ariaLabel="Test data table"
      />
    );

    const region = screen.getByRole('region', { name: 'Test data table' });
    expect(region).toBeInTheDocument();
  });

  it('should handle nested property access', () => {
    interface NestedData {
      id: number;
      user: {
        name: string;
      };
    }

    const nestedColumns: Column<NestedData>[] = [
      { id: 'id', label: 'ID' },
      { id: 'user.name', label: 'User Name' },
    ];

    const nestedData: NestedData[] = [
      { id: 1, user: { name: 'John' } },
      { id: 2, user: { name: 'Jane' } },
    ];

    render(<DataTable columns={nestedColumns} data={nestedData} />);

    expect(screen.getByText('John')).toBeInTheDocument();
    expect(screen.getByText('Jane')).toBeInTheDocument();
  });
});
