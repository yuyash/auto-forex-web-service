/**
 * WebSocketConnectionStatus Component
 *
 * Displays the current WebSocket connection status with visual indicators.
 * Shows different states: Connected, Reconnecting, and Offline (using polling fallback).
 *
 * Requirements: 3.5
 */

import { Box, Chip, Tooltip } from '@mui/material';
import { CheckCircle, Sync, CloudOff } from '@mui/icons-material';

export enum ConnectionState {
  CONNECTED = 'connected',
  RECONNECTING = 'reconnecting',
  OFFLINE = 'offline',
}

export interface WebSocketConnectionStatusProps {
  connectionState: ConnectionState;
  reconnectAttempts?: number;
  maxReconnectAttempts?: number;
}

/**
 * WebSocketConnectionStatus displays the current connection state
 * with appropriate icons and colors
 */
export const WebSocketConnectionStatus = ({
  connectionState,
  reconnectAttempts = 0,
  maxReconnectAttempts = 5,
}: WebSocketConnectionStatusProps) => {
  const getStatusConfig = () => {
    switch (connectionState) {
      case ConnectionState.CONNECTED:
        return {
          label: 'Connected',
          icon: <CheckCircle sx={{ fontSize: 16 }} />,
          color: 'success' as const,
          tooltip: 'Real-time updates active',
        };
      case ConnectionState.RECONNECTING:
        return {
          label: 'Reconnecting...',
          icon: (
            <Sync sx={{ fontSize: 16, animation: 'spin 1s linear infinite' }} />
          ),
          color: 'warning' as const,
          tooltip: `Attempting to reconnect (${reconnectAttempts}/${maxReconnectAttempts})`,
        };
      case ConnectionState.OFFLINE:
        return {
          label: 'Offline - Using polling',
          icon: <CloudOff sx={{ fontSize: 16 }} />,
          color: 'default' as const,
          tooltip: 'WebSocket unavailable, using polling fallback',
        };
      default:
        return {
          label: 'Unknown',
          icon: null,
          color: 'default' as const,
          tooltip: 'Connection status unknown',
        };
    }
  };

  const config = getStatusConfig();

  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        '@keyframes spin': {
          '0%': { transform: 'rotate(0deg)' },
          '100%': { transform: 'rotate(360deg)' },
        },
      }}
    >
      <Tooltip title={config.tooltip} arrow>
        <Chip
          icon={config.icon}
          label={config.label}
          color={config.color}
          size="small"
          sx={{
            height: 28,
            fontSize: '0.75rem',
            '& .MuiChip-icon': {
              marginLeft: '8px',
            },
          }}
        />
      </Tooltip>
    </Box>
  );
};

export default WebSocketConnectionStatus;
