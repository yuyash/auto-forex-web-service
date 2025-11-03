# Custom Hooks

This directory contains custom React hooks used throughout the application.

## useMarketData

A custom hook for connecting to the market data WebSocket and receiving real-time tick updates with throttling.

### Features

- **WebSocket Connection**: Automatically connects to the market data WebSocket endpoint
- **Throttling**: Limits updates to a maximum frequency (default: 100ms) to prevent excessive re-renders
- **Auto-Reconnection**: Automatically attempts to reconnect on connection loss with exponential backoff
- **Error Handling**: Comprehensive error handling with callbacks
- **Connection Status**: Provides real-time connection status
- **Manual Reconnect**: Exposes a reconnect function for manual reconnection

### Usage

```typescript
import useMarketData from '../hooks/useMarketData';

const MyComponent = () => {
  const { tickData, isConnected, error, reconnect } = useMarketData({
    accountId: 'my-account-id',
    instrument: 'EUR_USD',
    throttleMs: 100, // Optional, defaults to 100ms
    onError: (err) => console.error('WebSocket error:', err),
    onConnect: () => console.log('Connected'),
    onDisconnect: () => console.log('Disconnected'),
  });

  if (error) {
    return <div>Error: {error.message}</div>;
  }

  if (!isConnected) {
    return <div>Connecting...</div>;
  }

  return (
    <div>
      <p>Instrument: {tickData?.instrument}</p>
      <p>Mid Price: {tickData?.mid}</p>
      <p>Spread: {tickData?.spread}</p>
      <button onClick={reconnect}>Reconnect</button>
    </div>
  );
};
```

### Parameters

- `accountId` (string, required): The OANDA account ID
- `instrument` (string, required): The currency pair (e.g., 'EUR_USD')
- `throttleMs` (number, optional): Maximum update frequency in milliseconds (default: 100)
- `onError` (function, optional): Callback function called when an error occurs
- `onConnect` (function, optional): Callback function called when connection is established
- `onDisconnect` (function, optional): Callback function called when connection is closed

### Return Value

- `tickData` (TickData | null): The latest tick data received from the WebSocket
- `isConnected` (boolean): Whether the WebSocket is currently connected
- `error` (Error | null): Any error that occurred
- `reconnect` (function): Function to manually trigger a reconnection

### WebSocket Endpoint

The hook connects to: `wss://{host}/ws/market-data/{accountId}/{instrument}/`

### Throttling Behavior

The hook implements intelligent throttling:

- First tick is applied immediately
- Subsequent ticks within the throttle period are queued
- The last queued tick is applied after the throttle period expires
- This ensures smooth updates while preventing excessive re-renders

### Reconnection Strategy

- Automatic reconnection on connection loss
- Maximum 5 reconnection attempts
- 2-second delay between attempts
- Manual reconnection available via `reconnect()` function

## useSystemSettings

A custom hook for fetching system-wide settings like registration and login availability.

See the hook file for detailed documentation.
