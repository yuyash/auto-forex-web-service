import { useState, useEffect, useCallback } from 'react';
import {
  Container,
  Typography,
  Box,
  Paper,
  Stack,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  TextField,
  Button,
  Card,
  CardContent,
  Chip,
  Alert,
  CircularProgress,
  Divider,
  FormHelperText,
  type SelectChangeEvent,
} from '@mui/material';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../contexts/AuthContext';
import type {
  Strategy,
  StrategyConfig,
  StrategyStatus,
  Account,
} from '../types/strategy';

const StrategyPage = () => {
  const { t } = useTranslation('strategy');
  const { token } = useAuth();

  // State management
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [selectedAccount, setSelectedAccount] = useState<number | ''>('');
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [selectedStrategy, setSelectedStrategy] = useState<string>('');
  const [strategyConfig, setStrategyConfig] = useState<StrategyConfig>({});
  const [strategyStatus, setStrategyStatus] = useState<StrategyStatus | null>(
    null
  );
  const [instruments, setInstruments] = useState<string>('EUR_USD');

  // Loading and error states
  const [loading, setLoading] = useState(false);
  const [accountsLoading, setAccountsLoading] = useState(true);
  const [strategiesLoading, setStrategiesLoading] = useState(true);
  const [statusLoading, setStatusLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Fetch accounts
  const fetchAccounts = useCallback(async () => {
    if (!token) return;

    setAccountsLoading(true);
    try {
      const response = await fetch('/api/accounts/', {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (response.ok) {
        const data = await response.json();
        setAccounts(data);
        if (data.length > 0 && !selectedAccount) {
          setSelectedAccount(data[0].id);
        }
      } else {
        setError('Failed to load accounts');
      }
    } catch (err) {
      setError('Error loading accounts');
      console.error('Error fetching accounts:', err);
    } finally {
      setAccountsLoading(false);
    }
  }, [token, selectedAccount]);

  // Fetch available strategies
  const fetchStrategies = useCallback(async () => {
    if (!token) return;

    setStrategiesLoading(true);
    try {
      const response = await fetch('/api/strategies/', {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (response.ok) {
        const data = await response.json();
        setStrategies(data);
      } else {
        setError('Failed to load strategies');
      }
    } catch (err) {
      setError('Error loading strategies');
      console.error('Error fetching strategies:', err);
    } finally {
      setStrategiesLoading(false);
    }
  }, [token]);

  // Fetch strategy status for selected account
  const fetchStrategyStatus = useCallback(async () => {
    if (!token || !selectedAccount) return;

    setStatusLoading(true);
    try {
      const response = await fetch(
        `/api/accounts/${selectedAccount}/strategy/status/`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      if (response.ok) {
        const data = await response.json();
        setStrategyStatus(data);
        if (data.is_active && data.strategy_type) {
          setSelectedStrategy(data.strategy_type);
          setStrategyConfig(data.config || {});
          setInstruments(data.instruments?.join(',') || 'EUR_USD');
        }
      }
    } catch (err) {
      console.error('Error fetching strategy status:', err);
    } finally {
      setStatusLoading(false);
    }
  }, [token, selectedAccount]);

  // Load data on mount and when dependencies change
  useEffect(() => {
    fetchAccounts();
  }, [fetchAccounts]);

  useEffect(() => {
    fetchStrategies();
  }, [fetchStrategies]);

  useEffect(() => {
    if (selectedAccount) {
      fetchStrategyStatus();
    }
  }, [selectedAccount, fetchStrategyStatus]);

  // Handle account selection
  const handleAccountChange = (event: SelectChangeEvent<number | ''>) => {
    const value = event.target.value;
    setSelectedAccount(value === '' ? '' : Number(value));
    setError(null);
    setSuccessMessage(null);
  };

  // Handle strategy selection
  const handleStrategyChange = (event: SelectChangeEvent<string>) => {
    const strategyId = event.target.value;
    setSelectedStrategy(strategyId);

    // Initialize config with default values from schema
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
    setError(null);
  };

  // Handle config field changes
  const handleConfigChange = (field: string, value: unknown) => {
    setStrategyConfig((prev) => ({
      ...prev,
      [field]: value,
    }));
  };

  // Start strategy
  const handleStartStrategy = async () => {
    if (!token || !selectedAccount || !selectedStrategy) {
      setError('Please select an account and strategy');
      return;
    }

    setLoading(true);
    setError(null);
    setSuccessMessage(null);

    try {
      const response = await fetch(
        `/api/accounts/${selectedAccount}/strategy/start/`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            strategy_type: selectedStrategy,
            config: strategyConfig,
            instruments: instruments.split(',').map((i) => i.trim()),
          }),
        }
      );

      if (response.ok) {
        setSuccessMessage(t('messages.startSuccess'));
        await fetchStrategyStatus();
      } else {
        const data = await response.json();
        setError(data.error || 'Failed to start strategy');
      }
    } catch (err) {
      setError('Error starting strategy');
      console.error('Error starting strategy:', err);
    } finally {
      setLoading(false);
    }
  };

  // Stop strategy
  const handleStopStrategy = async () => {
    if (!token || !selectedAccount) {
      setError('Please select an account');
      return;
    }

    setLoading(true);
    setError(null);
    setSuccessMessage(null);

    try {
      const response = await fetch(
        `/api/accounts/${selectedAccount}/strategy/stop/`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
        }
      );

      if (response.ok) {
        setSuccessMessage(t('messages.stopSuccess'));
        await fetchStrategyStatus();
      } else {
        const data = await response.json();
        setError(data.error || 'Failed to stop strategy');
      }
    } catch (err) {
      setError('Error stopping strategy');
      console.error('Error stopping strategy:', err);
    } finally {
      setLoading(false);
    }
  };

  // Render config field based on schema
  const renderConfigField = (
    fieldName: string,
    fieldSchema: {
      type: string;
      description?: string;
      default?: unknown;
      minimum?: number;
      maximum?: number;
      enum?: string[];
    }
  ) => {
    const value = strategyConfig[fieldName] ?? fieldSchema.default ?? '';

    if (fieldSchema.enum) {
      return (
        <FormControl fullWidth key={fieldName}>
          <InputLabel>{fieldName}</InputLabel>
          <Select
            value={String(value)}
            label={fieldName}
            onChange={(e) => handleConfigChange(fieldName, e.target.value)}
            disabled={strategyStatus?.is_active}
          >
            {fieldSchema.enum.map((option) => (
              <MenuItem key={option} value={option}>
                {option}
              </MenuItem>
            ))}
          </Select>
          {fieldSchema.description && (
            <FormHelperText>{fieldSchema.description}</FormHelperText>
          )}
        </FormControl>
      );
    }

    if (fieldSchema.type === 'number' || fieldSchema.type === 'integer') {
      return (
        <TextField
          key={fieldName}
          fullWidth
          label={fieldName}
          type="number"
          value={value}
          onChange={(e) =>
            handleConfigChange(
              fieldName,
              fieldSchema.type === 'integer'
                ? parseInt(e.target.value, 10)
                : parseFloat(e.target.value)
            )
          }
          helperText={fieldSchema.description}
          inputProps={{
            min: fieldSchema.minimum,
            max: fieldSchema.maximum,
          }}
          disabled={strategyStatus?.is_active}
        />
      );
    }

    return (
      <TextField
        key={fieldName}
        fullWidth
        label={fieldName}
        value={value}
        onChange={(e) => handleConfigChange(fieldName, e.target.value)}
        helperText={fieldSchema.description}
        disabled={strategyStatus?.is_active}
      />
    );
  };

  const selectedStrategyData = strategies.find(
    (s) => s.id === selectedStrategy
  );

  return (
    <Container maxWidth={false} sx={{ mt: 4, mb: 4, px: 3 }}>
      <Typography variant="h4" gutterBottom>
        {t('title')}
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {successMessage && (
        <Alert
          severity="success"
          sx={{ mb: 2 }}
          onClose={() => setSuccessMessage(null)}
        >
          {successMessage}
        </Alert>
      )}

      <Stack spacing={3}>
        {/* Account Selection */}
        <Paper sx={{ p: 3 }}>
          <Typography variant="h6" gutterBottom>
            Account Selection
          </Typography>
          <FormControl fullWidth>
            <InputLabel>OANDA Account</InputLabel>
            <Select
              value={selectedAccount}
              label="OANDA Account"
              onChange={handleAccountChange}
              disabled={accountsLoading}
            >
              {accounts.map((account) => (
                <MenuItem key={account.id} value={account.id}>
                  {account.account_id} ({account.api_type}) - Balance:{' '}
                  {account.balance} {account.currency}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Paper>

        {/* Strategy Status */}
        {selectedAccount && (
          <Card>
            <CardContent>
              <Box
                display="flex"
                justifyContent="space-between"
                alignItems="center"
                mb={2}
              >
                <Typography variant="h6">
                  {t('status.notConfigured')}
                </Typography>
                {statusLoading ? (
                  <CircularProgress size={24} />
                ) : (
                  <Chip
                    label={
                      strategyStatus?.is_active
                        ? t('status.running')
                        : t('status.stopped')
                    }
                    color={strategyStatus?.is_active ? 'success' : 'default'}
                  />
                )}
              </Box>

              {strategyStatus?.is_active && strategyStatus.state && (
                <Box
                  display="flex"
                  gap={2}
                  flexWrap="wrap"
                  sx={{
                    '& > *': {
                      flex: { xs: '1 1 100%', sm: '1 1 calc(33.333% - 16px)' },
                    },
                  }}
                >
                  <Box>
                    <Typography variant="body2" color="text.secondary">
                      Strategy Type
                    </Typography>
                    <Typography variant="body1">
                      {strategyStatus.strategy_type}
                    </Typography>
                  </Box>
                  <Box>
                    <Typography variant="body2" color="text.secondary">
                      Positions
                    </Typography>
                    <Typography variant="body1">
                      {strategyStatus.state.positions_count}
                    </Typography>
                  </Box>
                  <Box>
                    <Typography variant="body2" color="text.secondary">
                      Total P&L
                    </Typography>
                    <Typography
                      variant="body1"
                      color={
                        strategyStatus.state.total_pnl >= 0
                          ? 'success.main'
                          : 'error.main'
                      }
                    >
                      {strategyStatus.state.total_pnl.toFixed(2)}
                    </Typography>
                  </Box>
                </Box>
              )}
            </CardContent>
          </Card>
        )}

        {/* Strategy Configuration */}
        {selectedAccount && !strategyStatus?.is_active && (
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              {t('configuration')}
            </Typography>

            <Stack spacing={2}>
              <FormControl fullWidth>
                <InputLabel>{t('selectStrategy')}</InputLabel>
                <Select
                  value={selectedStrategy}
                  label={t('selectStrategy')}
                  onChange={handleStrategyChange}
                  disabled={strategiesLoading}
                >
                  {strategies.map((strategy) => (
                    <MenuItem key={strategy.id} value={strategy.id}>
                      {strategy.name}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>

              {selectedStrategyData && (
                <Alert severity="info">
                  {selectedStrategyData.description}
                </Alert>
              )}

              <TextField
                fullWidth
                label={t('parameters.instruments')}
                value={instruments}
                onChange={(e) => setInstruments(e.target.value)}
                helperText="Comma-separated list (e.g., EUR_USD, GBP_USD)"
              />

              {selectedStrategyData && (
                <>
                  <Divider />
                  <Typography variant="subtitle1">
                    Strategy Parameters
                  </Typography>
                  <Box
                    display="flex"
                    gap={2}
                    flexWrap="wrap"
                    sx={{
                      '& > *': {
                        flex: { xs: '1 1 100%', sm: '1 1 calc(50% - 8px)' },
                      },
                    }}
                  >
                    {Object.entries(
                      selectedStrategyData.config_schema.properties || {}
                    ).map(([fieldName, fieldSchema]) => (
                      <Box key={fieldName}>
                        {renderConfigField(fieldName, fieldSchema)}
                      </Box>
                    ))}
                  </Box>
                </>
              )}

              <Box display="flex" gap={2}>
                <Button
                  variant="contained"
                  color="primary"
                  onClick={handleStartStrategy}
                  disabled={!selectedStrategy || loading}
                  startIcon={loading && <CircularProgress size={20} />}
                >
                  {t('control.start')}
                </Button>
              </Box>
            </Stack>
          </Paper>
        )}

        {/* Stop Strategy Button */}
        {selectedAccount && strategyStatus?.is_active && (
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Strategy Control
            </Typography>
            <Button
              variant="contained"
              color="error"
              onClick={handleStopStrategy}
              disabled={loading}
              startIcon={loading && <CircularProgress size={20} />}
            >
              {t('control.stop')}
            </Button>
          </Paper>
        )}
      </Stack>
    </Container>
  );
};

export default StrategyPage;
