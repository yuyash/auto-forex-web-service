import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import UserSessionList from '../components/admin/UserSessionList';
import type { UserSession } from '../types/admin';

const mockSessions: UserSession[] = [
  {
    id: 1,
    username: 'trader1',
    email: 'trader1@example.com',
    login_time: '2025-01-15T10:00:00Z',
    last_activity: '2025-01-15T10:30:00Z',
    ip_address: '192.168.1.100',
    session_count: 1,
  },
  {
    id: 2,
    username: 'trader2',
    email: 'trader2@example.com',
    login_time: '2025-01-15T09:00:00Z',
    last_activity: '2025-01-15T10:25:00Z',
    ip_address: '192.168.1.101',
    session_count: 2,
  },
  {
    id: 3,
    username: 'trader3',
    email: 'trader3@example.com',
    login_time: '2025-01-15T08:00:00Z',
    last_activity: '2025-01-15T10:20:00Z',
    ip_address: '192.168.1.102',
    session_count: 1,
  },
];

describe('UserSessionList', () => {
  it('renders user session list with all users', () => {
    const mockOnKickOff = vi.fn();
    render(
      <UserSessionList sessions={mockSessions} onKickOff={mockOnKickOff} />
    );

    expect(screen.getByText('Online Users')).toBeInTheDocument();
    expect(screen.getByText('trader1')).toBeInTheDocument();
    expect(screen.getByText('trader2')).toBeInTheDocument();
    expect(screen.getByText('trader3')).toBeInTheDocument();
    expect(screen.getByText('trader1@example.com')).toBeInTheDocument();
    expect(screen.getByText('trader2@example.com')).toBeInTheDocument();
    expect(screen.getByText('trader3@example.com')).toBeInTheDocument();
  });

  it('displays username for each session', () => {
    const mockOnKickOff = vi.fn();
    render(
      <UserSessionList sessions={mockSessions} onKickOff={mockOnKickOff} />
    );

    expect(screen.getByText('trader1')).toBeInTheDocument();
    expect(screen.getByText('trader2')).toBeInTheDocument();
    expect(screen.getByText('trader3')).toBeInTheDocument();
  });

  it('displays IP address for each session', () => {
    const mockOnKickOff = vi.fn();
    render(
      <UserSessionList sessions={mockSessions} onKickOff={mockOnKickOff} />
    );

    expect(screen.getByText('192.168.1.100')).toBeInTheDocument();
    expect(screen.getByText('192.168.1.101')).toBeInTheDocument();
    expect(screen.getByText('192.168.1.102')).toBeInTheDocument();
  });

  it('displays session count for each user', () => {
    const mockOnKickOff = vi.fn();
    render(
      <UserSessionList sessions={mockSessions} onKickOff={mockOnKickOff} />
    );

    // Session counts are displayed as chips
    const sessionChips = screen.getAllByText(/^[0-9]+$/);
    expect(sessionChips.length).toBeGreaterThan(0);
  });

  it('displays kick off button for each user', () => {
    const mockOnKickOff = vi.fn();
    render(
      <UserSessionList sessions={mockSessions} onKickOff={mockOnKickOff} />
    );

    const kickOffButtons = screen.getAllByText('Kick Off');
    expect(kickOffButtons).toHaveLength(mockSessions.length);
  });

  it('shows confirmation dialog when kick off button is clicked', async () => {
    const mockOnKickOff = vi.fn();
    render(
      <UserSessionList sessions={mockSessions} onKickOff={mockOnKickOff} />
    );

    const kickOffButtons = screen.getAllByText('Kick Off');
    fireEvent.click(kickOffButtons[0]);

    await waitFor(() => {
      expect(screen.getByText('Confirm Kick Off')).toBeInTheDocument();
    });
  });

  it('calls onKickOff when confirmed', async () => {
    const mockOnKickOff = vi.fn();
    render(
      <UserSessionList sessions={mockSessions} onKickOff={mockOnKickOff} />
    );

    const kickOffButtons = screen.getAllByText('Kick Off');
    fireEvent.click(kickOffButtons[0]);

    await waitFor(() => {
      expect(screen.getByText('Confirm Kick Off')).toBeInTheDocument();
    });

    const confirmButton = screen.getByRole('button', { name: /kick off/i });
    fireEvent.click(confirmButton);

    await waitFor(() => {
      expect(mockOnKickOff).toHaveBeenCalledWith(1);
    });
  });

  it('does not call onKickOff when cancelled', async () => {
    const mockOnKickOff = vi.fn();
    render(
      <UserSessionList sessions={mockSessions} onKickOff={mockOnKickOff} />
    );

    const kickOffButtons = screen.getAllByText('Kick Off');
    fireEvent.click(kickOffButtons[0]);

    await waitFor(() => {
      expect(screen.getByText('Confirm Kick Off')).toBeInTheDocument();
    });

    const cancelButton = screen.getByRole('button', { name: /cancel/i });
    fireEvent.click(cancelButton);

    await waitFor(() => {
      expect(mockOnKickOff).not.toHaveBeenCalled();
    });
  });

  it('displays empty state when no sessions', () => {
    const mockOnKickOff = vi.fn();
    render(<UserSessionList sessions={[]} onKickOff={mockOnKickOff} />);

    expect(screen.getByText('No users online')).toBeInTheDocument();
  });

  it('displays total session count badge', () => {
    const mockOnKickOff = vi.fn();
    render(
      <UserSessionList sessions={mockSessions} onKickOff={mockOnKickOff} />
    );

    // The badge showing total number of sessions (3 in this case)
    const badges = screen.getAllByText('3');
    expect(badges.length).toBeGreaterThan(0);
  });

  it('formats login time correctly', () => {
    const mockOnKickOff = vi.fn();
    render(
      <UserSessionList sessions={mockSessions} onKickOff={mockOnKickOff} />
    );

    // Check that dates are formatted (exact format depends on locale)
    const dateElements = screen.getAllByText(
      /\d{1,2}\/\d{1,2}\/\d{4}|\d{4}-\d{2}-\d{2}/
    );
    expect(dateElements.length).toBeGreaterThan(0);
  });

  it('displays last activity timestamp', () => {
    const mockOnKickOff = vi.fn();
    render(
      <UserSessionList sessions={mockSessions} onKickOff={mockOnKickOff} />
    );

    // Last activity should be displayed for each session
    const dateElements = screen.getAllByText(
      /\d{1,2}\/\d{1,2}\/\d{4}|\d{4}-\d{2}-\d{2}/
    );
    expect(dateElements.length).toBeGreaterThan(0);
  });
});
