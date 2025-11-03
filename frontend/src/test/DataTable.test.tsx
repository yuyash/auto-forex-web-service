import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect } from 'vitest';
import DataTable, { Column } from '../components/common/DataTable';

interface TestData {
  id: number;
  name: string;
  email: string;
  age: number;
}

const testData: TestData[] = [
  { id: 1, name: 'John Doe', email: 'john@example.com', age: 30 },
  { id: 2, name: 'Jane Smith', email: 'jane@example.com', age: 25 },
  { id: 3, name: 'Bob Johnson', email: 'bob@example.com', age: 35 },
];

const columns: Column<TestData>[] = [
  { id: 'id', label: 'ID', sortable: true },
  { id: 'name', label: 'Name', sortable: true, filterable: true },
  { id: 'email', label: 'Email', filterable: true },
  { id: 'age', label: 'Age', sortable: true },
];

describe('DataTable', () => {
  it('renders table with data', () => {
    render(<DataTable columns={columns} data={testData} />);
    expect(screen.getByText('John Doe')).toBeInTheDocument();
    expect(screen.getByText('Jane Smith')).toBeInTheDocument();
    expect(screen.getByText('Bob Johnson')).toBeInTheDocument();
  });

  it('shows empty message when no data', () => {
    render(<DataTable columns={columns} data={[]} />);
    expect(screen.getByText('No data available')).toBeInTheDocument();
  });

  it('filters data by name', async () => {
    const user = userEvent.setup();
    render(<DataTable columns={columns} data={testData} />);

    const nameFilter = screen.getByPlaceholderText('Filter Name');
    await user.type(nameFilter, 'John');

    expect(screen.getByText('John Doe')).toBeInTheDocument();
    expect(screen.queryByText('Jane Smith')).not.toBeInTheDocument();
  });

  it('sorts data when column header is clicked', async () => {
    const user = userEvent.setup();
    render(<DataTable columns={columns} data={testData} />);

    const ageHeader = screen.getByText('Age');
    await user.click(ageHeader);

    const rows = screen.getAllByRole('row');
    // First row is header, second is filter row, third is first data row
    expect(rows[2]).toHaveTextContent('Jane Smith');
  });

  it('changes page when pagination is used', async () => {
    const user = userEvent.setup();
    const largeData = Array.from({ length: 25 }, (_, i) => ({
      id: i + 1,
      name: `User ${i + 1}`,
      email: `user${i + 1}@example.com`,
      age: 20 + i,
    }));

    render(
      <DataTable columns={columns} data={largeData} defaultRowsPerPage={10} />
    );

    expect(screen.getByText('User 1')).toBeInTheDocument();
    expect(screen.queryByText('User 11')).not.toBeInTheDocument();

    const nextPageButton = screen.getByRole('button', { name: /next page/i });
    await user.click(nextPageButton);

    expect(screen.queryByText('User 1')).not.toBeInTheDocument();
    expect(screen.getByText('User 11')).toBeInTheDocument();
  });
});
