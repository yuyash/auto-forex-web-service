import React from 'react';
import {
  Timeline,
  TimelineItem,
  TimelineSeparator,
  TimelineConnector,
  TimelineContent,
  TimelineDot,
  TimelineOppositeContent,
} from '@mui/lab';
import { Typography, Box, Chip } from '@mui/material';
import {
  CheckCircle,
  Error,
  PlayArrow,
  Stop,
  Refresh,
} from '@mui/icons-material';
import type { TaskExecution } from '../../../types/execution';
import { TaskStatus } from '../../../types/common';
import { formatDistanceToNow } from 'date-fns';

interface ExecutionTimelineProps {
  executions: TaskExecution[];
  maxItems?: number;
  showMetrics?: boolean;
}

export const ExecutionTimeline: React.FC<ExecutionTimelineProps> = ({
  executions,
  maxItems = 10,
  showMetrics = true,
}) => {
  const displayExecutions = executions.slice(0, maxItems);

  const getStatusIcon = (status: TaskStatus) => {
    switch (status) {
      case TaskStatus.COMPLETED:
        return <CheckCircle />;
      case TaskStatus.FAILED:
        return <Error />;
      case TaskStatus.RUNNING:
        return <PlayArrow />;
      case TaskStatus.STOPPED:
        return <Stop />;
      default:
        return <Refresh />;
    }
  };

  const getStatusColor = (status: TaskStatus) => {
    switch (status) {
      case TaskStatus.COMPLETED:
        return 'success';
      case TaskStatus.FAILED:
        return 'error';
      case TaskStatus.RUNNING:
        return 'primary';
      case TaskStatus.STOPPED:
        return 'default';
      default:
        return 'grey';
    }
  };

  const formatDuration = (execution: TaskExecution): string => {
    if (!execution.completed_at) {
      return 'In progress';
    }

    const start = new Date(execution.started_at);
    const end = new Date(execution.completed_at);
    const durationMs = end.getTime() - start.getTime();

    const hours = Math.floor(durationMs / (1000 * 60 * 60));
    const minutes = Math.floor((durationMs % (1000 * 60 * 60)) / (1000 * 60));
    const seconds = Math.floor((durationMs % (1000 * 60)) / 1000);

    if (hours > 0) {
      return `${hours}h ${minutes}m`;
    } else if (minutes > 0) {
      return `${minutes}m ${seconds}s`;
    } else {
      return `${seconds}s`;
    }
  };

  if (displayExecutions.length === 0) {
    return (
      <Box sx={{ textAlign: 'center', py: 4 }}>
        <Typography variant="body2" color="text.secondary">
          No execution history available
        </Typography>
      </Box>
    );
  }

  return (
    <Timeline position="right">
      {displayExecutions.map((execution, index) => (
        <TimelineItem key={execution.id}>
          <TimelineOppositeContent color="text.secondary" sx={{ flex: 0.3 }}>
            <Typography variant="caption" display="block">
              {formatDistanceToNow(new Date(execution.started_at), {
                addSuffix: true,
              })}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {formatDuration(execution)}
            </Typography>
          </TimelineOppositeContent>

          <TimelineSeparator>
            <TimelineDot
              color={
                getStatusColor(execution.status) as
                  | 'primary'
                  | 'secondary'
                  | 'error'
                  | 'warning'
                  | 'info'
                  | 'success'
                  | 'grey'
              }
            >
              {getStatusIcon(execution.status)}
            </TimelineDot>
            {index < displayExecutions.length - 1 && <TimelineConnector />}
          </TimelineSeparator>

          <TimelineContent>
            <Box sx={{ mb: 2 }}>
              <Box
                sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}
              >
                <Typography variant="body1" sx={{ fontWeight: 500 }}>
                  Execution #{execution.execution_number}
                </Typography>
                <Chip
                  label={execution.status}
                  size="small"
                  color={
                    getStatusColor(execution.status) as
                      | 'primary'
                      | 'secondary'
                      | 'error'
                      | 'warning'
                      | 'info'
                      | 'success'
                      | 'default'
                  }
                />
              </Box>

              {execution.error_message && (
                <Typography variant="body2" color="error" sx={{ mb: 1 }}>
                  Error: {execution.error_message}
                </Typography>
              )}

              {showMetrics && execution.metrics && (
                <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', mt: 1 }}>
                  <Box>
                    <Typography variant="caption" color="text.secondary">
                      Return
                    </Typography>
                    <Typography
                      variant="body2"
                      sx={{
                        fontWeight: 600,
                        color:
                          parseFloat(execution.metrics.total_return) >= 0
                            ? 'success.main'
                            : 'error.main',
                      }}
                    >
                      {parseFloat(execution.metrics.total_return) >= 0
                        ? '+'
                        : ''}
                      {execution.metrics.total_return}%
                    </Typography>
                  </Box>
                  <Box>
                    <Typography variant="caption" color="text.secondary">
                      Trades
                    </Typography>
                    <Typography variant="body2" sx={{ fontWeight: 600 }}>
                      {execution.metrics.total_trades}
                    </Typography>
                  </Box>
                  <Box>
                    <Typography variant="caption" color="text.secondary">
                      Win Rate
                    </Typography>
                    <Typography variant="body2" sx={{ fontWeight: 600 }}>
                      {execution.metrics.win_rate}%
                    </Typography>
                  </Box>
                </Box>
              )}
            </Box>
          </TimelineContent>
        </TimelineItem>
      ))}

      {executions.length > maxItems && (
        <TimelineItem>
          <TimelineOppositeContent sx={{ flex: 0.3 }} />
          <TimelineSeparator>
            <TimelineDot color="grey" />
          </TimelineSeparator>
          <TimelineContent>
            <Typography variant="body2" color="text.secondary">
              {executions.length - maxItems} more execution
              {executions.length - maxItems > 1 ? 's' : ''}
            </Typography>
          </TimelineContent>
        </TimelineItem>
      )}
    </Timeline>
  );
};
