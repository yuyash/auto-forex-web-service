import React, { useEffect, useRef, useState, useCallback } from 'react';
import {
  Box,
  Paper,
  Typography,
  Checkbox,
  FormControlLabel,
  IconButton,
  Tooltip,
} from '@mui/material';
import { Clear } from '@mui/icons-material';

interface LogEntry {
  timestamp: string;
  level: string;
  message: string;
}

export interface LogPanelProps {
  taskType: 'backtest' | 'trading';
  taskId: string;
  maxEntries?: number;
  autoScroll?: boolean;
  showTimestamp?: boolean;
  height?: number | string;
}

/**
 * Component for displaying real-time log streaming from task execution.
 *
 * Features:
 * - Subscribe to execution_log WebSocket messages
 * - Display logs with timestamp, level (INFO/WARNING/ERROR), and message
 * - Color coding for log levels (red for ERROR, yellow for WARNING)
 * - Auto-scroll to latest log entry
 * - Auto-scroll toggle checkbox
 * - Maintain last 1000 log entries in memory
 * - Allow scrolling through historical logs
 * - Filter logs by task_id to show only relevant logs
 *
 * Requirements: 6.7, 6.8, 6.9, 6.10
 */
export const LogPanel: React.FC<LogPanelProps> = ({
  maxEntries = 1000,
  autoScroll: initialAutoScroll = true,
  showTimestamp = true,
  height = 400,
}) => {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [autoScroll, setAutoScroll] = useState(initialAutoScroll);
  const logContainerRef = useRef<HTMLDivElement>(null);
  const isUserScrollingRef = useRef(false);

  // Auto-scroll to latest log entry when new logs arrive
  useEffect(() => {
    if (autoScroll && !isUserScrollingRef.current && logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [logs, autoScroll]);

  // Detect user scrolling to temporarily disable auto-scroll
  const handleScroll = useCallback(() => {
    if (!logContainerRef.current) return;

    const { scrollTop, scrollHeight, clientHeight } = logContainerRef.current;
    const isAtBottom = scrollHeight - scrollTop - clientHeight < 10;

    // If user scrolls away from bottom, mark as user scrolling
    if (!isAtBottom && autoScroll) {
      isUserScrollingRef.current = true;
    } else if (isAtBottom) {
      isUserScrollingRef.current = false;
    }
  }, [autoScroll]);

  // Clear all logs
  const handleClearLogs = useCallback(() => {
    setLogs([]);
  }, []);

  // Get color for log level
  const getLogLevelColor = (level: string): string => {
    const upperLevel = level.toUpperCase();
    if (upperLevel === 'ERROR') return '#f44336'; // Red
    if (upperLevel === 'WARNING' || upperLevel === 'WARN') return '#ff9800'; // Yellow/Orange
    if (upperLevel === 'INFO') return '#2196f3'; // Blue
    return '#9e9e9e'; // Gray for DEBUG or other levels
  };

  // Format timestamp for display
  const formatTimestamp = (timestamp: string): string => {
    try {
      const date = new Date(timestamp);
      return date.toLocaleTimeString('en-US', {
        hour12: false,
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        fractionalSecondDigits: 3,
      });
    } catch {
      return timestamp;
    }
  };

  return (
    <Paper
      elevation={2}
      sx={{
        p: 2,
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
      }}
    >
      {/* Header with controls */}
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          mb: 1,
        }}
      >
        <Typography variant="h6" component="h3">
          Execution Logs
        </Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <FormControlLabel
            control={
              <Checkbox
                checked={autoScroll}
                onChange={(e) => {
                  setAutoScroll(e.target.checked);
                  isUserScrollingRef.current = false;
                }}
                size="small"
              />
            }
            label="Auto-scroll"
            sx={{ mr: 0 }}
          />
          <Tooltip title="Clear logs">
            <IconButton
              size="small"
              onClick={handleClearLogs}
              disabled={logs.length === 0}
              aria-label="Clear logs"
            >
              <Clear />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      {/* Log entries container */}
      <Box
        ref={logContainerRef}
        onScroll={handleScroll}
        sx={{
          flex: 1,
          overflowY: 'auto',
          bgcolor: 'background.default',
          borderRadius: 1,
          p: 1,
          fontFamily: 'monospace',
          fontSize: '0.875rem',
          height: typeof height === 'number' ? `${height}px` : height,
          minHeight: 200,
          '&::-webkit-scrollbar': {
            width: '8px',
          },
          '&::-webkit-scrollbar-track': {
            bgcolor: 'background.paper',
          },
          '&::-webkit-scrollbar-thumb': {
            bgcolor: 'action.disabled',
            borderRadius: '4px',
            '&:hover': {
              bgcolor: 'action.active',
            },
          },
        }}
      >
        {logs.length === 0 ? (
          <Typography
            variant="body2"
            color="text.secondary"
            sx={{ fontStyle: 'italic', textAlign: 'center', mt: 2 }}
          >
            No logs yet. Logs will appear here when the task starts executing.
          </Typography>
        ) : (
          logs.map((log, index) => (
            <Box
              key={index}
              sx={{
                display: 'flex',
                gap: 1,
                py: 0.25,
                '&:hover': {
                  bgcolor: 'action.hover',
                },
              }}
            >
              {/* Timestamp */}
              {showTimestamp && (
                <Typography
                  component="span"
                  sx={{
                    color: 'text.secondary',
                    minWidth: '90px',
                    flexShrink: 0,
                  }}
                >
                  {formatTimestamp(log.timestamp)}
                </Typography>
              )}

              {/* Log level */}
              <Typography
                component="span"
                sx={{
                  color: getLogLevelColor(log.level),
                  fontWeight: 600,
                  minWidth: '70px',
                  flexShrink: 0,
                }}
              >
                {log.level.toUpperCase()}
              </Typography>

              {/* Log message */}
              <Typography
                component="span"
                sx={{
                  color: 'text.primary',
                  wordBreak: 'break-word',
                  flex: 1,
                }}
              >
                {log.message}
              </Typography>
            </Box>
          ))
        )}
      </Box>

      {/* Footer with log count */}
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          mt: 1,
        }}
      >
        <Typography variant="caption" color="text.secondary">
          {logs.length} {logs.length === 1 ? 'entry' : 'entries'}
          {logs.length >= maxEntries && ` (showing last ${maxEntries})`}
        </Typography>
      </Box>
    </Paper>
  );
};
