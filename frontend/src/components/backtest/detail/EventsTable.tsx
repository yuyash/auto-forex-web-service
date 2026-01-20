/**
 * EventsTable Component
 *
 * Displays strategy events in table format with pagination and real-time updates.
 * Fetches from GET /executions/<execution_id>/events/ using generated client.
 *
 * Requirements: 11.7
 */

import React, { useState, useEffect, useCallback } from 'react';
import { Box, Chip, Typography } from '@mui/material';
import DataTable, { type Column } from '../../common/DataTable';
import { ExecutionsService } from '../../../api/generated/services/ExecutionsService';
import { useToast } from '../../common';

interface StrategyEvent {
  id: number;
  timestamp: string;
  event_type: string;
  sequence: number;
  data: Record<string, unknown>;
}

interface EventsTableProps {
  executionId: number;
  enableRealTimeUpdates?: boolean;
}

/**
 * EventsTable Component
 *
 * Displays strategy events for an execution with real-time updates.
 *
 * @param executionId - The execution ID to fetch events for
 * @param enableRealTimeUpdates - Enable automatic refresh every 5 seconds
 */
export const EventsTable: React.FC<EventsTableProps> = ({
  executionId,
  enableRealTimeUpdates = false,
}) => {
  const [events, setEvents] = useState<StrategyEvent[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const { showError } = useToast();

  const fetchEvents = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const response = await ExecutionsService.getExecutionEvents(executionId);
      setEvents(response.events || []);
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : 'Failed to load events';
      setError(new Error(errorMessage));
      showError(errorMessage);
    } finally {
      setIsLoading(false);
    }
  }, [executionId, showError]);

  useEffect(() => {
    fetchEvents();
  }, [executionId, fetchEvents]);

  const formatTimestamp = (timestamp: string): string => {
    return new Date(timestamp).toLocaleString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  };

  const getEventTypeColor = (
    eventType: string
  ):
    | 'default'
    | 'primary'
    | 'secondary'
    | 'success'
    | 'error'
    | 'warning'
    | 'info' => {
    const lowerType = eventType.toLowerCase();
    if (lowerType.includes('error') || lowerType.includes('fail')) {
      return 'error';
    }
    if (lowerType.includes('warning')) {
      return 'warning';
    }
    if (lowerType.includes('success') || lowerType.includes('complete')) {
      return 'success';
    }
    if (lowerType.includes('signal') || lowerType.includes('entry')) {
      return 'primary';
    }
    if (lowerType.includes('exit') || lowerType.includes('close')) {
      return 'secondary';
    }
    return 'default';
  };

  const columns: Column<StrategyEvent>[] = [
    {
      id: 'sequence',
      label: 'Sequence',
      sortable: true,
      align: 'right',
      minWidth: 100,
    },
    {
      id: 'timestamp',
      label: 'Timestamp',
      sortable: true,
      minWidth: 200,
      render: (row) => formatTimestamp(row.timestamp),
    },
    {
      id: 'event_type',
      label: 'Event Type',
      sortable: true,
      filterable: true,
      minWidth: 180,
      render: (row) => (
        <Chip
          label={row.event_type}
          size="small"
          color={getEventTypeColor(row.event_type)}
        />
      ),
    },
    {
      id: 'data',
      label: 'Details',
      minWidth: 300,
      render: (row) => (
        <Box>
          {row.data &&
            Object.entries(row.data).map(([key, value]) => (
              <Typography
                key={key}
                variant="caption"
                component="div"
                sx={{ color: 'text.secondary' }}
              >
                <strong>{key}:</strong> {String(value)}
              </Typography>
            ))}
        </Box>
      ),
    },
  ];

  return (
    <DataTable
      columns={columns}
      data={events}
      isLoading={isLoading}
      error={error}
      emptyMessage="No strategy events found"
      enableRealTimeUpdates={enableRealTimeUpdates}
      onRefresh={fetchEvents}
      ariaLabel="Strategy events table"
      defaultRowsPerPage={25}
      rowsPerPageOptions={[10, 25, 50, 100]}
    />
  );
};

export default EventsTable;
