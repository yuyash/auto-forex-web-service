import { useState } from 'react';
import {
  Box,
  TextField,
  Button,
  Typography,
  Stack,
  Autocomplete,
  Chip,
  Alert,
  Divider,
  FormControl,
  FormHelperText,
} from '@mui/material';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { useTranslation } from 'react-i18next';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import type { Strategy, StrategyConfig } from '../../types/strategy';
import type { BacktestConfig } from '../../types/backtest';
import StrategySelector from '../strategy/StrategySelector';
import StrategyConfigForm from '../strategy/StrategyConfigForm';

interface BacktestConfigPanelProps {
  strategies: Strategy[];
  onRunBacktest: (config: BacktestConfig) => void;
  loading?: boolean;
  disabled?: boolean;
}

// Common forex currency pairs
const AVAILABLE_INSTRUMENT = [
  'JPY_USD',
  'EUR_USD',
  'GBP_USD',
  'USD_JPY',
  'USD_CHF',
  'AUD_USD',
  'USD_CAD',
  'NZD_USD',
  'EUR_GBP',
  'EUR_JPY',
  'GBP_JPY',
  'EUR_CHF',
  'AUD_JPY',
  'GBP_AUD',
  'EUR_AUD',
  'CHF_JPY',
];

const BacktestConfigPanel = ({
  strategies,
  onRunBacktest,
  loading = false,
  disabled = false,
}: BacktestConfigPanelProps) => {
  const { t } = useTranslation(['backtest', 'common']);

  // Strategy selection
  const [selectedStrategy, setSelectedStrategy] = useState<string>('floor');
  const [strategyConfig, setStrategyConfig] = useState<StrategyConfig>({});

  // Backtest parameters
  const [instrument, setInstrument] = useState<string>('USD_JPY');
  const [startDate, setStartDate] = useState<Date | null>(() => {
    const date = new Date();
    date.setDate(date.getDate() - 30); // 30 days ago
    return date;
  });
  const [endDate, setEndDate] = useState<Date | null>(() => new Date());
  const [initialBalance, setInitialBalance] = useState<number>(10000);
  const [commission, setCommission] = useState<number>(0.0);

  // Validation
  const [showValidation, setShowValidation] = useState(false);
  const [validationErrors, setValidationErrors] = useState<string[]>([]);

  // Get selected strategy data
  const selectedStrategyData = strategies.find(
    (s) => s.id === selectedStrategy
  );

  // Handle strategy change
  const handleStrategyChange = (strategyId: string) => {
    setSelectedStrategy(strategyId);

    // Initialize strategy config with defaults
    const strategy = strategies.find((s) => s.id === strategyId);
    if (strategy) {
      const defaultConfig: StrategyConfig = {};
      Object.entries(strategy.config_schema.properties || {}).forEach(
        ([key, prop]) => {
          if (prop.default !== undefined) {
            defaultConfig[key] = prop.default;
          }
        }
      );
      setStrategyConfig(defaultConfig);
    }
  };

  // Validate form
  const validateForm = (): boolean => {
    const errors: string[] = [];

    if (!selectedStrategy) {
      errors.push(
        t('backtest:validation.strategyRequired', 'Please select a strategy')
      );
    }

    if (!instrument) {
      errors.push(
        t(
          'backtest:validation.instrumentRequired',
          'Please select an instrument'
        )
      );
    }

    if (!startDate) {
      errors.push(
        t('backtest:validation.startDateRequired', 'Please select a start date')
      );
    }

    if (!endDate) {
      errors.push(
        t('backtest:validation.endDateRequired', 'Please select an end date')
      );
    }

    if (startDate && endDate && startDate >= endDate) {
      errors.push(
        t(
          'backtest:validation.dateRangeInvalid',
          'Start date must be before end date'
        )
      );
    }

    if (initialBalance <= 0) {
      errors.push(
        t(
          'backtest:validation.initialBalanceInvalid',
          'Initial balance must be greater than 0'
        )
      );
    }

    if (commission < 0) {
      errors.push(
        t(
          'backtest:validation.commissionInvalid',
          'Commission cannot be negative'
        )
      );
    }

    setValidationErrors(errors);
    return errors.length === 0;
  };

  // Handle run backtest
  const handleRunBacktest = () => {
    setShowValidation(true);

    if (!validateForm()) {
      return;
    }

    if (!startDate || !endDate) {
      return;
    }

    const config: BacktestConfig = {
      strategy_type: selectedStrategy,
      config: strategyConfig,
      instrument,
      data_source: 'postgresql',
      start_date: startDate.toISOString().split('T')[0],
      end_date: endDate.toISOString().split('T')[0],
      initial_balance: initialBalance,
      commission,
    };

    onRunBacktest(config);
  };

  return (
    <Box>
      <Typography variant="h6" gutterBottom>
        {t('backtest:config.title', 'Backtest Configuration')}
      </Typography>

      <Divider sx={{ mb: 3 }} />

      {/* Validation Errors */}
      {showValidation && validationErrors.length > 0 && (
        <Alert severity="error" sx={{ mb: 2 }}>
          <Typography variant="subtitle2" gutterBottom>
            {t(
              'backtest:validation.errors',
              'Please fix the following errors:'
            )}
          </Typography>
          <ul style={{ margin: 0, paddingLeft: 20 }}>
            {validationErrors.map((error, index) => (
              <li key={index}>{error}</li>
            ))}
          </ul>
        </Alert>
      )}

      <Stack spacing={3}>
        {/* Strategy Selector */}
        <Box>
          <Typography variant="subtitle2" gutterBottom>
            {t('backtest:config.strategy', 'Strategy')} *
          </Typography>
          <StrategySelector
            strategies={strategies}
            selectedStrategy={selectedStrategy}
            onStrategyChange={handleStrategyChange}
            disabled={disabled || loading}
            loading={loading}
            variant="dropdown"
          />
        </Box>

        {/* Strategy Configuration */}
        {selectedStrategyData && (
          <Box>
            <StrategyConfigForm
              configSchema={selectedStrategyData.config_schema}
              config={strategyConfig}
              onChange={setStrategyConfig}
              disabled={disabled || loading}
              showValidation={showValidation}
            />
          </Box>
        )}

        {/* Data Source Selector */}
        <FormControl fullWidth disabled={disabled || loading}>
          <FormHelperText>
            {t(
              'backtest:config.dataSourceHelp',
              'Using PostgreSQL for backtesting'
            )}
          </FormHelperText>
        </FormControl>

        {/* Instrument Selector */}
        <Box>
          <Typography variant="subtitle2" gutterBottom>
            {t('backtest:config.instrument', 'Instrument')} *
          </Typography>
          <Autocomplete
            options={AVAILABLE_INSTRUMENT}
            value={instrument}
            onChange={(_event, newValue) =>
              setInstrument(newValue || 'USD_JPY')
            }
            disabled={disabled || loading}
            renderInput={(params) => (
              <TextField
                {...params}
                placeholder={t(
                  'backtest:config.instrumentPlaceholder',
                  'Select currency pair'
                )}
                helperText={t(
                  'backtest:config.instrumentHelp',
                  'Select a currency pair to backtest'
                )}
              />
            )}
            renderTags={(value, getTagProps) =>
              value.map((option, index) => (
                <Chip
                  label={option}
                  {...getTagProps({ index })}
                  key={option}
                  size="small"
                />
              ))
            }
          />
        </Box>

        {/* Date Range */}
        <LocalizationProvider dateAdapter={AdapterDateFns}>
          <Box>
            <Typography variant="subtitle2" gutterBottom>
              {t('backtest:config.dateRange', 'Date Range')} *
            </Typography>
            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
              <DatePicker
                label={t('backtest:config.startDate', 'Start Date')}
                value={startDate}
                onChange={setStartDate}
                disabled={disabled || loading}
                slotProps={{
                  textField: {
                    fullWidth: true,
                    helperText: t(
                      'backtest:config.startDateHelp',
                      'Backtest start date'
                    ),
                  },
                }}
              />
              <DatePicker
                label={t('backtest:config.endDate', 'End Date')}
                value={endDate}
                onChange={setEndDate}
                disabled={disabled || loading}
                slotProps={{
                  textField: {
                    fullWidth: true,
                    helperText: t(
                      'backtest:config.endDateHelp',
                      'Backtest end date'
                    ),
                  },
                }}
              />
            </Stack>
          </Box>
        </LocalizationProvider>

        {/* Initial Balance */}
        <TextField
          fullWidth
          label={t('backtest:config.initialBalance', 'Initial Balance')}
          type="number"
          value={initialBalance}
          onChange={(e) => setInitialBalance(parseFloat(e.target.value))}
          disabled={disabled || loading}
          helperText={t(
            'backtest:config.initialBalanceHelp',
            'Starting account balance for the backtest'
          )}
          inputProps={{ min: 0, step: 100 }}
          required
        />

        {/* Commission */}
        <TextField
          fullWidth
          label={t('backtest:config.commission', 'Commission per Trade')}
          type="number"
          value={commission}
          onChange={(e) => setCommission(parseFloat(e.target.value))}
          disabled={disabled || loading}
          helperText={t(
            'backtest:config.commissionHelp',
            'Commission charged per trade (bid/ask spread already included in tick data)'
          )}
          inputProps={{ min: 0, step: 0.01 }}
        />

        {/* Run Backtest Button */}
        <Button
          variant="contained"
          color="primary"
          size="large"
          fullWidth
          onClick={handleRunBacktest}
          disabled={disabled || loading}
          startIcon={<PlayArrowIcon />}
        >
          {loading
            ? t('backtest:config.running', 'Running...')
            : t('backtest:config.runBacktest', 'Run Backtest')}
        </Button>
      </Stack>
    </Box>
  );
};

export default BacktestConfigPanel;
