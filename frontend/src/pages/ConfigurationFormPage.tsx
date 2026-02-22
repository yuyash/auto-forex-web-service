import { useEffect, useState } from 'react';
import {
  Container,
  Paper,
  Typography,
  Box,
  Alert,
  CircularProgress,
} from '@mui/material';
import { useNavigate, useParams, useLocation } from 'react-router-dom';
import { Breadcrumbs } from '../components/common';
import ConfigurationForm from '../components/configurations/ConfigurationForm';
import { useConfiguration } from '../hooks/useConfigurations';
import { useConfigurationMutations } from '../hooks/useConfigurationMutations';
import type { StrategyConfigCreateData } from '../types/configuration';

const ConfigurationFormPage = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { id } = useParams<{ id: string }>();
  const isEditMode = Boolean(id);

  // Get navigation state to determine where we came from
  const fromState = location.state as {
    from?: 'backtest-tasks' | 'trading-tasks';
    taskId?: number;
    taskName?: string;
  } | null;
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Fetch configuration if editing
  const configId = id || undefined;
  const { data: configuration, isLoading: isLoadingConfig } =
    useConfiguration(configId);

  const { createConfiguration, updateConfiguration, isCreating, isUpdating } =
    useConfigurationMutations();

  // Redirect if configuration not found in edit mode
  useEffect(() => {
    if (isEditMode && !isLoadingConfig && !configuration) {
      navigate('/configurations');
    }
  }, [isEditMode, isLoadingConfig, configuration, navigate]);

  const handleSubmit = async (data: StrategyConfigCreateData) => {
    setErrorMessage(null);
    try {
      await createConfiguration(data);
      navigate('/configurations');
    } catch (err: unknown) {
      console.error('Failed to save configuration:', err);

      // Type assertion for error object with data property
      const error = err as {
        data?: {
          name?: string[];
          strategy_type?: string[];
          parameters?: string | Record<string, unknown>;
          error?: string;
          detail?: string;
        };
        message?: string;
      };

      // Extract error message from API response
      if (error.data) {
        // Handle field-specific errors
        if (error.data.name && Array.isArray(error.data.name)) {
          setErrorMessage(error.data.name[0]);
        } else if (
          error.data.strategy_type &&
          Array.isArray(error.data.strategy_type)
        ) {
          setErrorMessage(error.data.strategy_type[0]);
        } else if (error.data.parameters) {
          setErrorMessage(
            typeof error.data.parameters === 'string'
              ? error.data.parameters
              : 'Invalid parameters'
          );
        } else if (error.data.error) {
          setErrorMessage(error.data.error);
        } else if (error.data.detail) {
          setErrorMessage(error.data.detail);
        } else {
          setErrorMessage(error.message || 'Failed to save configuration');
        }
      } else {
        setErrorMessage(error.message || 'Failed to save configuration');
      }
    }
  };

  const handleCancel = () => {
    navigate('/configurations');
  };

  if (isEditMode && isLoadingConfig) {
    return (
      <Container maxWidth="md" sx={{ mt: 4, mb: 4 }}>
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
          <CircularProgress />
        </Box>
      </Container>
    );
  }

  return (
    <Container maxWidth="md" sx={{ mt: 4, mb: 4, px: 3 }}>
      <Breadcrumbs
        customPath={
          fromState?.from
            ? [
                {
                  label:
                    fromState.from === 'backtest-tasks'
                      ? 'Backtest Tasks'
                      : 'Trading Tasks',
                  path: `/${fromState.from}`,
                },
                ...(fromState.taskId && fromState.taskName
                  ? [
                      {
                        label: fromState.taskName,
                        path: `/${fromState.from}/${fromState.taskId}`,
                      },
                    ]
                  : []),
              ]
            : undefined
        }
      />

      <Box sx={{ mb: 4 }}>
        <Typography variant="h4" gutterBottom>
          {isEditMode ? 'Edit Strategy Parameters' : 'Create New Configuration'}
        </Typography>
        <Typography variant="body1" color="text.secondary">
          {isEditMode
            ? 'Update the parameters for your strategy configuration'
            : 'Create a reusable strategy configuration for backtesting and live trading'}
        </Typography>
      </Box>

      {isEditMode && !configuration && !isLoadingConfig && (
        <Alert severity="error" sx={{ mb: 3 }}>
          Configuration not found
        </Alert>
      )}

      {errorMessage && (
        <Alert
          severity="error"
          sx={{ mb: 3 }}
          onClose={() => setErrorMessage(null)}
        >
          {errorMessage}
        </Alert>
      )}

      <Paper elevation={2} sx={{ p: 4 }}>
        {isEditMode && configuration ? (
          <ConfigurationForm
            mode="edit"
            initialData={{
              name: configuration.name,
              strategy_type: configuration.strategy_type,
              description: configuration.description,
              parameters: configuration.parameters,
            }}
            onSubmit={async (data) => {
              await updateConfiguration({
                id: configuration.id,
                data: {
                  parameters: data.parameters,
                },
              });
              navigate('/configurations');
            }}
            onCancel={handleCancel}
            isLoading={isUpdating}
          />
        ) : (
          <ConfigurationForm
            mode="create"
            onSubmit={handleSubmit}
            onCancel={handleCancel}
            isLoading={isCreating}
          />
        )}
      </Paper>
    </Container>
  );
};

export default ConfigurationFormPage;
