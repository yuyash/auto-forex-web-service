import { useEffect, useMemo, useState } from 'react';
import { Paper, Typography, Box, Alert, CircularProgress } from '@mui/material';
import { useNavigate, useParams, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Breadcrumbs, PageContainer } from '../components/common';
import ConfigurationForm from '../components/configurations/ConfigurationForm';
import { useConfiguration } from '../hooks/useConfigurations';
import { useConfigurationMutations } from '../hooks/useConfigurationMutations';
import type { StrategyConfigCreateData } from '../types/configuration';
import { logger } from '../utils/logger';

const ConfigurationFormPage = () => {
  const { t } = useTranslation(['configuration', 'common']);
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
  const isEditLocked = Boolean(isEditMode && configuration?.has_running_tasks);

  // Build form initial data ONCE from the initial configuration response.
  // React Query may refetch this configuration in the background (e.g. when
  // the tab regains focus or after a polling interval). Recomputing the
  // initialData object on every refetch would cause ConfigurationForm to
  // discard whatever the user is currently typing.  We therefore capture a
  // stable snapshot keyed on the primitive values we actually care about.
  // parameters is a JSON object; stringify so referential changes from the
  // cache don't trigger resets when the content is unchanged.
  const parametersSignature = JSON.stringify(configuration?.parameters ?? {});
  const editInitialData = useMemo(() => {
    if (!isEditMode || !configuration) return undefined;
    return {
      name: configuration.name,
      strategy_type: configuration.strategy_type,
      description: configuration.description,
      parameters: configuration.parameters,
    };
    // We deliberately exclude `configuration` reference changes to avoid
    // resetting the form while the user is editing. The `configuration.id`
    // will only change if the user navigates to a different configuration,
    // which remounts this page anyway.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    isEditMode,
    configuration?.id,
    configuration?.name,
    configuration?.strategy_type,
    configuration?.description,
    parametersSignature,
  ]);

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
      logger.error('Failed to save configuration', {
        error: err instanceof Error ? err.message : String(err),
      });

      // Type assertion for error object with data property
      const error = err as {
        data?: {
          name?: string[];
          strategy_type?: string[];
          parameters?: string | Record<string, unknown>;
          error?: string;
          detail?: string | string[];
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
          setErrorMessage(
            Array.isArray(error.data.detail)
              ? error.data.detail[0]
              : error.data.detail
          );
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
      <PageContainer sx={{ mt: 4, mb: 4 }}>
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
          <CircularProgress />
        </Box>
      </PageContainer>
    );
  }

  return (
    <PageContainer sx={{ mt: 4, mb: 4 }}>
      <Breadcrumbs
        customPath={
          fromState?.from
            ? [
                {
                  label:
                    fromState.from === 'backtest-tasks'
                      ? t('common:navigation.backtestTasks')
                      : t('common:navigation.tradingTasks'),
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
          {isEditMode
            ? t('configuration:pages.editTitle')
            : t('configuration:pages.createTitle')}
        </Typography>
        <Typography variant="body1" color="text.secondary">
          {isEditMode
            ? t('configuration:pages.editSubtitle')
            : t('configuration:pages.createSubtitle')}
        </Typography>
      </Box>

      {isEditMode && !configuration && !isLoadingConfig && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {t('common:errors.taskNotFound')}
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

      {isEditLocked && (
        <Alert severity="warning" sx={{ mb: 3 }}>
          {t('configuration:form.editLockedRunningTasks')}
        </Alert>
      )}

      <Paper elevation={2} sx={{ p: 4 }}>
        {isEditMode && configuration && !isEditLocked ? (
          <ConfigurationForm
            mode="edit"
            initialData={editInitialData}
            onSubmit={async (data) => {
              try {
                await updateConfiguration({
                  id: configuration.id,
                  data: {
                    parameters: data.parameters,
                  },
                });
                navigate('/configurations');
              } catch (err: unknown) {
                const error = err as {
                  data?: { detail?: string | string[] };
                  message?: string;
                };
                if (error.data?.detail) {
                  setErrorMessage(
                    Array.isArray(error.data.detail)
                      ? error.data.detail[0]
                      : error.data.detail
                  );
                } else {
                  setErrorMessage(
                    error.message || 'Failed to save configuration'
                  );
                }
              }
            }}
            onCancel={handleCancel}
            isLoading={isUpdating}
          />
        ) : isEditMode && isEditLocked ? (
          <Box />
        ) : (
          <ConfigurationForm
            mode="create"
            onSubmit={handleSubmit}
            onCancel={handleCancel}
            isLoading={isCreating}
          />
        )}
      </Paper>
    </PageContainer>
  );
};

export default ConfigurationFormPage;
