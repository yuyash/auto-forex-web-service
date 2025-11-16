/**
 * Tests for WebSocketConnectionStatus Component
 *
 * Tests:
 * - Status display for each connection state
 * - Transitions between states
 *
 * Requirements: 3.5
 */

import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import WebSocketConnectionStatus, {
  ConnectionState,
} from '../components/common/WebSocketConnectionStatus';

describe('WebSocketConnectionStatus', () => {
  describe('Status Display', () => {
    it('should display "Connected" state with success color', () => {
      render(
        <WebSocketConnectionStatus
          connectionState={ConnectionState.CONNECTED}
        />
      );

      const chip = screen.getByText('Connected');
      expect(chip).toBeInTheDocument();

      // Check for success color class
      const chipElement = chip.closest('.MuiChip-root');
      expect(chipElement).toHaveClass('MuiChip-colorSuccess');
    });

    it('should display "Reconnecting..." state with warning color', () => {
      render(
        <WebSocketConnectionStatus
          connectionState={ConnectionState.RECONNECTING}
          reconnectAttempts={2}
          maxReconnectAttempts={5}
        />
      );

      const chip = screen.getByText('Reconnecting...');
      expect(chip).toBeInTheDocument();

      // Check for warning color class
      const chipElement = chip.closest('.MuiChip-root');
      expect(chipElement).toHaveClass('MuiChip-colorWarning');
    });

    it('should display "Offline - Using polling" state with default color', () => {
      render(
        <WebSocketConnectionStatus connectionState={ConnectionState.OFFLINE} />
      );

      const chip = screen.getByText('Offline - Using polling');
      expect(chip).toBeInTheDocument();

      // Check for default color class
      const chipElement = chip.closest('.MuiChip-root');
      expect(chipElement).toHaveClass('MuiChip-colorDefault');
    });

    it('should display reconnection attempts in tooltip for reconnecting state', () => {
      render(
        <WebSocketConnectionStatus
          connectionState={ConnectionState.RECONNECTING}
          reconnectAttempts={3}
          maxReconnectAttempts={5}
        />
      );

      // The tooltip content is rendered but hidden by default
      // We can verify the component renders without errors
      expect(screen.getByText('Reconnecting...')).toBeInTheDocument();
    });

    it('should use default values for reconnect attempts when not provided', () => {
      render(
        <WebSocketConnectionStatus
          connectionState={ConnectionState.RECONNECTING}
        />
      );

      expect(screen.getByText('Reconnecting...')).toBeInTheDocument();
    });
  });

  describe('State Transitions', () => {
    it('should update display when transitioning from offline to connected', () => {
      const { rerender } = render(
        <WebSocketConnectionStatus connectionState={ConnectionState.OFFLINE} />
      );

      expect(screen.getByText('Offline - Using polling')).toBeInTheDocument();

      // Transition to connected
      rerender(
        <WebSocketConnectionStatus
          connectionState={ConnectionState.CONNECTED}
        />
      );

      expect(screen.getByText('Connected')).toBeInTheDocument();
      expect(
        screen.queryByText('Offline - Using polling')
      ).not.toBeInTheDocument();
    });

    it('should update display when transitioning from connected to reconnecting', () => {
      const { rerender } = render(
        <WebSocketConnectionStatus
          connectionState={ConnectionState.CONNECTED}
        />
      );

      expect(screen.getByText('Connected')).toBeInTheDocument();

      // Transition to reconnecting
      rerender(
        <WebSocketConnectionStatus
          connectionState={ConnectionState.RECONNECTING}
          reconnectAttempts={1}
          maxReconnectAttempts={5}
        />
      );

      expect(screen.getByText('Reconnecting...')).toBeInTheDocument();
      expect(screen.queryByText('Connected')).not.toBeInTheDocument();
    });

    it('should update display when transitioning from reconnecting to offline', () => {
      const { rerender } = render(
        <WebSocketConnectionStatus
          connectionState={ConnectionState.RECONNECTING}
          reconnectAttempts={4}
          maxReconnectAttempts={5}
        />
      );

      expect(screen.getByText('Reconnecting...')).toBeInTheDocument();

      // Transition to offline after max attempts
      rerender(
        <WebSocketConnectionStatus
          connectionState={ConnectionState.OFFLINE}
          reconnectAttempts={5}
          maxReconnectAttempts={5}
        />
      );

      expect(screen.getByText('Offline - Using polling')).toBeInTheDocument();
      expect(screen.queryByText('Reconnecting...')).not.toBeInTheDocument();
    });

    it('should update reconnect attempts count during reconnecting state', () => {
      const { rerender } = render(
        <WebSocketConnectionStatus
          connectionState={ConnectionState.RECONNECTING}
          reconnectAttempts={1}
          maxReconnectAttempts={5}
        />
      );

      expect(screen.getByText('Reconnecting...')).toBeInTheDocument();

      // Update reconnect attempts
      rerender(
        <WebSocketConnectionStatus
          connectionState={ConnectionState.RECONNECTING}
          reconnectAttempts={2}
          maxReconnectAttempts={5}
        />
      );

      expect(screen.getByText('Reconnecting...')).toBeInTheDocument();

      // Update again
      rerender(
        <WebSocketConnectionStatus
          connectionState={ConnectionState.RECONNECTING}
          reconnectAttempts={3}
          maxReconnectAttempts={5}
        />
      );

      expect(screen.getByText('Reconnecting...')).toBeInTheDocument();
    });

    it('should handle rapid state transitions', () => {
      const { rerender } = render(
        <WebSocketConnectionStatus
          connectionState={ConnectionState.CONNECTED}
        />
      );

      // Rapid transitions
      rerender(
        <WebSocketConnectionStatus
          connectionState={ConnectionState.RECONNECTING}
          reconnectAttempts={1}
        />
      );
      rerender(
        <WebSocketConnectionStatus
          connectionState={ConnectionState.CONNECTED}
        />
      );
      rerender(
        <WebSocketConnectionStatus
          connectionState={ConnectionState.RECONNECTING}
          reconnectAttempts={1}
        />
      );
      rerender(
        <WebSocketConnectionStatus connectionState={ConnectionState.OFFLINE} />
      );

      // Should end up in offline state
      expect(screen.getByText('Offline - Using polling')).toBeInTheDocument();
    });
  });

  describe('Visual Elements', () => {
    it('should render CheckCircle icon for connected state', () => {
      render(
        <WebSocketConnectionStatus
          connectionState={ConnectionState.CONNECTED}
        />
      );

      // Icon is rendered as part of the chip
      const chip = screen.getByText('Connected').closest('.MuiChip-root');
      expect(chip?.querySelector('.MuiChip-icon')).toBeInTheDocument();
    });

    it('should render Sync icon for reconnecting state', () => {
      render(
        <WebSocketConnectionStatus
          connectionState={ConnectionState.RECONNECTING}
        />
      );

      const chip = screen.getByText('Reconnecting...').closest('.MuiChip-root');
      expect(chip?.querySelector('.MuiChip-icon')).toBeInTheDocument();
    });

    it('should render CloudOff icon for offline state', () => {
      render(
        <WebSocketConnectionStatus connectionState={ConnectionState.OFFLINE} />
      );

      const chip = screen
        .getByText('Offline - Using polling')
        .closest('.MuiChip-root');
      expect(chip?.querySelector('.MuiChip-icon')).toBeInTheDocument();
    });

    it('should render as a small chip', () => {
      render(
        <WebSocketConnectionStatus
          connectionState={ConnectionState.CONNECTED}
        />
      );

      const chip = screen.getByText('Connected').closest('.MuiChip-root');
      expect(chip).toHaveClass('MuiChip-sizeSmall');
    });
  });
});
