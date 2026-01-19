// EventFeed component - displays recent events in a scrolling list
import React, { useRef, useEffect } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  List,
  ListItem,
  ListItemText,
  Chip,
  Skeleton,
  Paper,
} from '@mui/material';
import {
  TrendingUp as LongIcon,
  TrendingDown as ShortIcon,
  AddCircle as LayerIcon,
  RemoveCircle as CloseIcon,
  MonetizationOn as ProfitIcon,
  Lock as LockIcon,
  Warning as WarningIcon,
} from '@mui/icons-material';
import { useExecutionEvents } from '../../../hooks/useExecutionEvents';
import { formatDateTime, formatCurrency } from '../../../utils/formatters';
import type { BacktestStrategyEvent } from '../../../types';

interface EventFeedProps {
  executionId: number;
  maxHeight?: number;
  autoScroll?: boolean;
}

const eventTypeConfig: Record<
  string,
  { label: string; color: string; icon: React.ReactNode }
> = {
  initial: {
    label: 'Initial Position',
    color: 'primary',
    icon: <LayerIcon />,
  },
  retracement: {
    label: 'Retracement',
    color: 'info',
    icon: <LayerIcon />,
  },
  layer: {
    label: 'Layer Added',
    color: 'success',
    icon: <LayerIcon />,
  },
  close: {
    label: 'Position Closed',
    color: 'default',
    icon: <CloseIcon />,
  },
  take_profit: {
    label: 'Take Profit',
    color: 'success',
    icon: <ProfitIcon />,
  },
  volatility_lock: {
    label: 'Volatility Lock',
    color: 'warning',
    icon: <LockIcon />,
  },
  margin_protection: {
    label: 'Margin Protection',
    color: 'error',
    icon: <WarningIcon />,
  },
};

const EventItem: React.FC<{ event: BacktestStrategyEvent }> = ({ event }) => {
  const config = eventTypeConfig[event.event_type] || {
    label: event.event_type,
    color: 'default',
    icon: null,
  };

  const getEventDetails = () => {
    const details: string[] = [];

    if (event.layer_number != null) {
      details.push(`Layer ${event.layer_number}`);
    }

    if (event.retracement_count != null) {
      details.push(`Retracement ${event.retracement_count}`);
    }

    if (event.direction) {
      details.push(event.direction.toUpperCase());
    }

    if (event.units) {
      details.push(`${event.units} units`);
    }

    if (event.price) {
      details.push(`@ ${event.price}`);
    }

    if (event.pnl) {
      const pnl = parseFloat(String(event.pnl));
      details.push(`P&L: ${formatCurrency(pnl)}`);
    }

    if (event.pips) {
      details.push(`${event.pips} pips`);
    }

    return details.join(' • ');
  };

  const DirectionIcon = event.direction === 'long' ? LongIcon : ShortIcon;

  return (
    <ListItem
      sx={{
        borderLeft: 3,
        borderColor: `${config.color}.main`,
        mb: 1,
        bgcolor: 'background.paper',
        borderRadius: 1,
      }}
    >
      <ListItemText
        primary={
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
            <Chip
              label={config.label}
              size="small"
              color={
                config.color as
                  | 'default'
                  | 'primary'
                  | 'secondary'
                  | 'error'
                  | 'info'
                  | 'success'
                  | 'warning'
              }
              icon={config.icon as React.ReactElement}
            />
            {event.direction && (
              <DirectionIcon
                fontSize="small"
                color={event.direction === 'long' ? 'success' : 'error'}
              />
            )}
            <Typography variant="caption" color="text.secondary">
              {event.timestamp && formatDateTime(event.timestamp)}
            </Typography>
          </Box>
        }
        secondary={
          <Typography variant="body2" color="text.secondary">
            {getEventDetails()}
          </Typography>
        }
      />
    </ListItem>
  );
};

export const EventFeed: React.FC<EventFeedProps> = ({
  executionId,
  maxHeight = 600,
  autoScroll = true,
}) => {
  const { events, isLoading, error } = useExecutionEvents(executionId);
  const listRef = useRef<HTMLDivElement>(null);
  const prevCountRef = useRef(events.length);

  // Auto-scroll to bottom when new events arrive
  useEffect(() => {
    if (autoScroll && events.length > prevCountRef.current && listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
    prevCountRef.current = events.length;
  }, [events.length, autoScroll]);

  if (error) {
    return (
      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Event Feed
          </Typography>
          <Typography color="error">
            Failed to load events: {error.message}
          </Typography>
        </CardContent>
      </Card>
    );
  }

  if (isLoading) {
    return (
      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Event Feed
          </Typography>
          <Box>
            {[1, 2, 3, 4, 5].map((i) => (
              <Skeleton
                key={i}
                variant="rectangular"
                height={60}
                sx={{ mb: 1 }}
              />
            ))}
          </Box>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardContent>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2 }}>
          <Typography variant="h6">Event Feed</Typography>
          <Chip label={`${events.length} events`} size="small" />
        </Box>

        {events.length === 0 ? (
          <Paper
            sx={{
              p: 3,
              textAlign: 'center',
              bgcolor: 'background.default',
            }}
          >
            <Typography color="text.secondary">
              No events yet. Events will appear here as the execution
              progresses.
            </Typography>
          </Paper>
        ) : (
          <Box
            ref={listRef}
            sx={{
              maxHeight,
              overflowY: 'auto',
              '&::-webkit-scrollbar': {
                width: '8px',
              },
              '&::-webkit-scrollbar-track': {
                bgcolor: 'background.default',
              },
              '&::-webkit-scrollbar-thumb': {
                bgcolor: 'divider',
                borderRadius: '4px',
              },
            }}
          >
            <List disablePadding>
              {events.map((event, index) => (
                <EventItem key={index} event={event} />
              ))}
            </List>
          </Box>
        )}
      </CardContent>
    </Card>
  );
};
