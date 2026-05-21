import { Add, Delete } from '@mui/icons-material';
import {
  Box,
  Button,
  FormControl,
  IconButton,
  InputLabel,
  MenuItem,
  Select,
  Typography,
} from '@mui/material';
import Grid from '@mui/material/Grid';
import { useTranslation } from 'react-i18next';
import { TIMEZONES } from '../../constants/timezones';
import type {
  BacktestClosedWindow,
  BacktestMarketClosure,
} from '../../types/backtestTask';
import { DateRangePicker } from '../tasks/forms/DateRangePicker';

interface MarketClosedWindowsEditorProps {
  value: BacktestMarketClosure[] | undefined;
  onChange: (value: BacktestMarketClosure[]) => void;
  defaultTimezone: string;
  error?: boolean;
  helperText?: string;
}

function isClosedWindow(
  value: BacktestMarketClosure
): value is BacktestClosedWindow {
  return Boolean(value && typeof value === 'object');
}

function splitClosures(value: BacktestMarketClosure[] | undefined): {
  legacyDates: string[];
  windows: BacktestClosedWindow[];
} {
  const items = Array.isArray(value) ? value : [];
  return {
    legacyDates: items.filter(
      (item): item is string => typeof item === 'string'
    ),
    windows: items.filter(isClosedWindow),
  };
}

function emptyWindow(timezone: string): BacktestClosedWindow {
  return {
    start: '',
    end: '',
    timezone,
  };
}

export function MarketClosedWindowsEditor({
  value,
  onChange,
  defaultTimezone,
  error = false,
  helperText,
}: MarketClosedWindowsEditorProps) {
  const { t } = useTranslation(['backtest', 'common']);
  const { legacyDates, windows } = splitClosures(value);

  const updateWindows = (nextWindows: BacktestClosedWindow[]) => {
    onChange([...legacyDates, ...nextWindows]);
  };

  const handleAdd = () => {
    updateWindows([...windows, emptyWindow(defaultTimezone || 'UTC')]);
  };

  const handleUpdate = (
    index: number,
    patch: Partial<BacktestClosedWindow>
  ) => {
    updateWindows(
      windows.map((window, currentIndex) =>
        currentIndex === index ? { ...window, ...patch } : window
      )
    );
  };

  const handleRemove = (index: number) => {
    updateWindows(windows.filter((_, currentIndex) => currentIndex !== index));
  };

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1.5 }}>
        <Typography
          variant="subtitle2"
          color={error ? 'error' : 'text.secondary'}
        >
          {t('backtest:form.excludedDates')}
        </Typography>
        <Button startIcon={<Add />} size="small" onClick={handleAdd}>
          {t('backtest:form.closedWindowAdd')}
        </Button>
      </Box>

      {legacyDates.length > 0 ? (
        <Typography
          variant="caption"
          color="text.secondary"
          sx={{ display: 'block', mb: 1.5 }}
        >
          {t('backtest:form.legacyExcludedDatesNotice', {
            dates: legacyDates.join(', '),
          })}
        </Typography>
      ) : null}

      {windows.length === 0 ? (
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          {t('backtest:form.closedWindowEmpty')}
        </Typography>
      ) : null}

      {windows.map((window, index) => (
        <Box
          key={index}
          sx={{
            border: 1,
            borderColor: error ? 'error.main' : 'divider',
            borderRadius: 1,
            p: 2,
            mb: 2,
          }}
        >
          <Grid container spacing={2} alignItems="flex-start">
            <Grid size={{ xs: 12 }}>
              <Typography variant="body2" color="text.secondary">
                {t('backtest:form.closedWindowNumber', {
                  number: index + 1,
                })}
              </Typography>
            </Grid>
            <Grid size={{ xs: 12, md: 8 }}>
              <DateRangePicker
                startDate={window.start || null}
                endDate={window.end || null}
                onStartDateChange={(date) =>
                  handleUpdate(index, {
                    start: typeof date === 'string' ? date : '',
                  })
                }
                onEndDateChange={(date) =>
                  handleUpdate(index, {
                    end: typeof date === 'string' ? date : '',
                  })
                }
                startLabel={t('backtest:form.closedWindowStart')}
                endLabel={t('backtest:form.closedWindowEnd')}
                timezone={window.timezone || defaultTimezone || 'UTC'}
              />
            </Grid>
            <Grid size={{ xs: 12, md: 3 }}>
              <FormControl fullWidth>
                <InputLabel id={`closed-window-timezone-${index}`}>
                  {t('backtest:form.closedWindowTimezone')}
                </InputLabel>
                <Select
                  labelId={`closed-window-timezone-${index}`}
                  value={window.timezone || defaultTimezone || 'UTC'}
                  label={t('backtest:form.closedWindowTimezone')}
                  onChange={(event) =>
                    handleUpdate(index, { timezone: event.target.value })
                  }
                >
                  {TIMEZONES.map((timezone) => (
                    <MenuItem key={timezone} value={timezone}>
                      {timezone}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            <Grid
              size={{ xs: 12, md: 1 }}
              sx={{
                display: 'flex',
                justifyContent: { xs: 'flex-start', md: 'center' },
              }}
            >
              <IconButton
                aria-label={t('backtest:form.closedWindowRemove')}
                color="error"
                onClick={() => handleRemove(index)}
              >
                <Delete />
              </IconButton>
            </Grid>
          </Grid>
        </Box>
      ))}

      {helperText ? (
        <Typography
          variant="caption"
          color={error ? 'error' : 'text.secondary'}
          sx={{ display: 'block', ml: 1.75 }}
        >
          {helperText}
        </Typography>
      ) : null}
    </Box>
  );
}
