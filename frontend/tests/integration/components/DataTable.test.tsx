/**
 * Integration tests for DataTable component.
 * Verifies rendering, sorting, pagination, filtering, empty/error/loading states.
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import DataTable, {
  type Column,
} from '../../../src/components/common/DataTable';

interface TestRow {
  id: number;
  name: string;
  value: number;
}

const columns: Column<TestRow>[] = [
  { id: 'id', label: 'ID', sortable: true },
  { id: 'name', label: 'Name', sortable: true, filterable: true },
  { id: 'value', label: 'Value', sortable: true },
];

const data: TestRow[] = [
  { id: 1, name: 'Alpha', value: 30 },
  { id: 2, name: 'Beta', value: 10 },
  { id: 3, name: 'Gamma', value: 20 },
];

describe('DataTable', () => {
  it('renders column headers', () => {
    render(<DataTable columns={columns} data={data} />);
    expect(screen.getByText('ID')).toBeInTheDocument();
    expect(screen.getByText('Name')).toBeInTheDocument();
    expect(screen.getByText('Value')).toBeInTheDocument();
  });

  it('renders data rows', () => {
    render(<DataTable columns={columns} data={data} />);
    expect(screen.getByText('Alpha')).toBeInTheDocument();
    expect(screen.getByText('Beta')).toBeInTheDocument();
    expect(screen.getByText('Gamma')).toBeInTheDocument();
  });

  it('shows empty message when no data', () => {
    render(
      <DataTable columns={columns} data={[]} emptyMessage="Nothing here" />
    );
    expect(screen.getByText('Nothing here')).toBeInTheDocument();
  });

  it('shows error state', () => {
    render(
      <DataTable columns={columns} data={[]} error={new Error('Load failed')} />
    );
    expect(screen.getByText('Load failed')).toBeInTheDocument();
  });

  it('shows loading skeleton when loading with no data', () => {
    render(<DataTable columns={columns} data={[]} isLoading />);
    // Skeleton rows should be present (MUI Skeleton)
    const skeletons = document.querySelectorAll('.MuiSkeleton-root');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it('sorts data when clicking column header', async () => {
    const user = userEvent.setup();
    render(<DataTable columns={columns} data={data} />);

    // Click "Value" to sort ascending
    await user.click(screen.getByText('Value'));

    const rows = screen.getAllByRole('row');
    // First row is header (+ optional filter row), data rows follow
    const dataRows = rows.filter((row) =>
      within(row).queryByText(/Alpha|Beta|Gamma/)
    );
    const firstDataCell = within(dataRows[0]).getByText(/Alpha|Beta|Gamma/);
    // After ascending sort by value: Beta(10), Gamma(20), Alpha(30)
    expect(firstDataCell.textContent).toBe('Beta');
  });

  it('calls onRowClick when a row is clicked', async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    render(<DataTable columns={columns} data={data} onRowClick={onClick} />);

    await user.click(screen.getByText('Alpha'));
    expect(onClick).toHaveBeenCalledWith(data[0]);
  });

  it('filters data by column value', async () => {
    const user = userEvent.setup();
    render(<DataTable columns={columns} data={data} />);

    const filterInput = screen.getByPlaceholderText('Filter Name');
    await user.type(filterInput, 'gam');

    expect(screen.getByText('Gamma')).toBeInTheDocument();
    expect(screen.queryByText('Alpha')).not.toBeInTheDocument();
    expect(screen.queryByText('Beta')).not.toBeInTheDocument();
  });

  it('paginates data', async () => {
    const manyRows = Array.from({ length: 15 }, (_, i) => ({
      id: i + 1,
      name: `Row ${i + 1}`,
      value: i,
    }));

    render(
      <DataTable columns={columns} data={manyRows} defaultRowsPerPage={10} />
    );

    // First page should show 10 rows
    expect(screen.getByText('Row 1')).toBeInTheDocument();
    expect(screen.getByText('Row 10')).toBeInTheDocument();
    expect(screen.queryByText('Row 11')).not.toBeInTheDocument();
  });

  it('has accessible region role', () => {
    render(<DataTable columns={columns} data={data} ariaLabel="Test table" />);
    expect(
      screen.getByRole('region', { name: 'Test table' })
    ).toBeInTheDocument();
  });
});
