// EventTimeline component - displays complete event history with filtering
import React, { useState, useMemo } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  List,
  ListItem,
  Chip,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Button,
  IconButton,
  Tooltip,
  Stack,
  Paper,
  Divider,
} from '@mui/material';
import {
  TrendingUp as LongIcon,
  TrendingDown as ShortIcon,
  AddCircle as LayerIcon,
  RemoveCircle as CloseIcon,
  MonetizationOn as ProfitIcon,
  Lock as LockIcon,
  Warning as WarningIcon,
  FilterList as FilterIcon,
  Clear as ClearIcon,
  Timeline as TimelineIcon,
} from '@mui/icons-material';
import { formatDateTime, formatCurrency } from '../../../utils/formatters';
import type { BacktestStrategyEvent } from '../../../types';

interface EventTimelineProps {
  events: BacktestStrategyEvent[];
  isLoading?: boolean;
}

type EventTypeFilter = 'all' | string;

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

const EventItem: React.FC<{ event: BacktestStrategyEvent; index: number }> = ({
  event,
  index,
}) => {
  const config = eventTypeConfig[event.event_type] || {
    label: event.event_type,
    color: 'default',
    icon: <TimelineIcon />,
  };

  const getEventDetails = () => {
    const details: string[] = [];

    if (event.layer_number != null) {
      details.push(`Layer ${event.layer_number}`);
    }

    if (event.retracement_count != null) {
      details.push(`Retracement ${event.retracement_count}`);
      if (event.max_retracements_per_layer != null) {
        details.push(`(max: ${event.max_retracements_per_layer})`);
      }
    }

    if (event.direction) {
      details.push(event.direction.toUpperCase());
    }

    if (event.units) {
      details.push(`${event.units} units`);
    }

    if (event.entry_price) {
      details.push(`Entry: ${event.entry_price}`);
    }

    if (event.exit_price) {
      details.push(`Exit: ${event.exit_price}`);
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

    if (event.entry_time) {
      details.push(`Entry: ${formatDateTime(event.entry_time)}`);
    }

    if (event.exit_time) {
      details.push(`Exit: ${formatDateTime(event.exit_time)}`);
    }

    return details;
  };

  const DirectionIcon = event.direction === 'long' ? LongIcon : ShortIcon;
  const details = getEventDetails();

  return (
    <ListItem
      sx={{
        display: 'flex',
        alignItems: 'flex-start',
        borderLeft: 3,
        borderColor: `${config.color}.main`,
        mb: 2,
        bgcolor: 'background.paper',
        borderRadius: 1,
        position: 'relative',
        '&::before': {
          content: '""',
          position: 'absolute',
          left: -10,
          top: 20,
          width: 16,
          height: 16,
          borderRadius: '50%',
          bgcolor: `${config.color}.main`,
          border: 2,
          borderColor: 'background.paper',
        },
      }}
    >
      <Box sx={{ width: '100%' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
          <Typography
            variant="caption"
            color="text.disabled"
            sx={{ minWidth: 40 }}
          >
            #{index + 1}
          </Typography>
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
          <Typography
            variant="caption"
            color="text.secondary"
            sx={{ ml: 'auto' }}
          >
            {event.timestamp && formatDateTime(event.timestamp)}
          </Typography>
        </Box>

        {details.length > 0 && (
          <Box sx={{ pl: 5 }}>
            {details.map((detail, idx) => (
              <Typography
                key={idx}
                variant="body2"
                color="text.secondary"
                sx={{ mb: 0.5 }}
              >
                • {detail}
              </Typography>
            ))}
          </Box>
        )}

        {event.instrument && (
          <Box sx={{ pl: 5, mt: 1 }}>
            <Chip label={event.instrument} size="small" variant="outlined" />
          </Box>
        )}
      </Box>
    </ListItem>
  );
};

export const EventTimeline: React.FC<EventTimelineProps> = ({
  events,
  isLoading = false,
}) => {
  const [eventTypeFilter, setEventTypeFilter] =
    useState<EventTypeFilter>('all');
  const [showFilters, setShowFilters] = useState(false);

  // Get unique event types
  const eventTypes = useMemo(() => {
    const uniqueTypes = new Set(events.map((e) => e.event_type));
    return Array.from(uniqueTypes).sort();
  }, [events]);

  // Apply filters
  const filteredEvents = useMemo(() => {
    let filtered = [...events];

    if (eventTypeFilter !== 'all') {
      filtered = filtered.filter((e) => e.event_type === eventTypeFilter);
    }

    return filtered;
  }, [events, eventTypeFilter]);

  const handleClearFilters = () => {
    setEventTypeFilter('all');
  };

  const activeFiltersCount = [eventTypeFilter !== 'all'].filter(Boolean).length;

  // Group events by date
  const groupedEvents = useMemo(() => {
    const groups: Record<string, BacktestStrategyEvent[]> = {};

    filteredEvents.forEach((event) => {
      if (!event.timestamp) return;
      const date = new Date(event.timestamp).toLocaleDateString();
      if (!groups[date]) {
        groups[date] = [];
      }
      groups[date].push(event);
    });

    return groups;
  }, [filteredEvents]);

  const eventStats = useMemo(() => {
    const stats: Record<string, number> = {};
    events.forEach((event) => {
      stats[event.event_type] = (stats[event.event_type] || 0) + 1;
    });
    return stats;
  }, [events]);

  if (isLoading) {
    return (
      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Event Timeline
          </Typography>
          <Typography color="text.secondary">Loading events...</Typography>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardContent>
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            mb: 2,
          }}
        >
          <Typography variant="h6">Event Timeline</Typography>

          <Box sx={{ display: 'flex', gap: 1 }}>
            <Tooltip title={showFilters ? 'Hide Filters' : 'Show Filters'}>
              <IconButton
                onClick={() => setShowFilters(!showFilters)}
                size="small"
              >
                <FilterIcon />
                {activeFiltersCount > 0 && (
                  <Chip
                    label={activeFiltersCount}
                    size="small"
                    color="primary"
                    sx={{
                      position: 'absolute',
                      top: -5,
                      right: -5,
                      height: 18,
                      minWidth: 18,
                    }}
                  />
                )}
              </IconButton>
            </Tooltip>
          </Box>
        </Box>

        {/* Event Statistics */}
        <Box
          sx={{ mb: 2, p: 2, bgcolor: 'background.default', borderRadius: 1 }}
        >
          <Typography variant="subtitle2" gutterBottom>
            Event Summary
          </Typography>
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
            {Object.entries(eventStats).map(([type, count]) => {
              const config = eventTypeConfig[type] || {
                label: type,
                color: 'default',
              };
              return (
                <Chip
                  key={type}
                  label={`${config.label}: ${count}`}
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
                  variant="outlined"
                />
              );
            })}
          </Box>
        </Box>

        {/* Filters */}
        {showFilters && (
          <Box
            sx={{ mb: 2, p: 2, bgcolor: 'background.default', borderRadius: 1 }}
          >
            <Stack spacing={2}>
              <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                <FormControl size="small" sx={{ minWidth: 200 }}>
                  <InputLabel>Event Type</InputLabel>
                  <Select
                    value={eventTypeFilter}
                    label="Event Type"
                    onChange={(e) => setEventTypeFilter(e.target.value)}
                  >
                    <MenuItem value="all">All Event Types</MenuItem>
                    {eventTypes.map((type) => {
                      const config = eventTypeConfig[type] || { label: type };
                      return (
                        <MenuItem key={type} value={type}>
                          {config.label}
                        </MenuItem>
                      );
                    })}
                  </Select>
                </FormControl>

                {activeFiltersCount > 0 && (
                  <Button
                    variant="outlined"
                    startIcon={<ClearIcon />}
                    onClick={handleClearFilters}
                    size="small"
                  >
                    Clear Filters
                  </Button>
                )}
              </Box>

              <Typography variant="body2" color="text.secondary">
                Showing {filteredEvents.length} of {events.length} events
              </Typography>
            </Stack>
          </Box>
        )}

        {filteredEvents.length === 0 ? (
          <Paper
            sx={{
              p: 3,
              textAlign: 'center',
              bgcolor: 'background.default',
            }}
          >
            <Typography color="text.secondary">
              {events.length === 0
                ? 'No events available'
                : 'No events match the selected filters'}
            </Typography>
          </Paper>
        ) : (
          <Box
            sx={{
              maxHeight: 800,
              overflowY: 'auto',
              pl: 2,
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
            {Object.entries(groupedEvents).map(([date, dateEvents]) => (
              <Box key={date} sx={{ mb: 3 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                  <Divider sx={{ flexGrow: 1 }} />
                  <Typography
                    variant="subtitle2"
                    color="text.secondary"
                    sx={{ px: 2, bgcolor: 'background.paper' }}
                  >
                    {date}
                  </Typography>
                  <Divider sx={{ flexGrow: 1 }} />
                </Box>
                <List disablePadding>
                  {dateEvents.map((event, index) => (
                    <EventItem
                      key={index}
                      event={event}
                      index={filteredEvents.indexOf(event)}
                    />
                  ))}
                </List>
              </Box>
            ))}
          </Box>
        )}
      </CardContent>
    </Card>
  );
};
