import { useEffect } from 'react';
import {
  Container,
  Paper,
  Typography,
  Box,
  Alert,
  CircularProgress,
} from '@mui/material';
import { useNavigate, useParams } from 'react-router-dom';
import { Breadcrumbs } from '../components/common';
import ConfigurationForm from '../components/configurations/ConfigurationForm';
import { useConfiguration } from '../hooks/useConfigurations';
import { useConfigurationMutations } from '../hooks/useConfigurationMutations';
import type { StrategyConfigCreateData } from '../types/configuration';

const ConfigurationFormPage = () => {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const isEditMode = Boolean(id);

  // Fetch configuration if editing
  const { data: configuration, isLoading: isLoadingConfig } = useConfiguration(
    Number(id) || 0
  );

  const { createConfiguration, updateConfiguration, isCreating, isUpdating } =
    useConfigurationMutations();

  const isLoading = isCreating || isUpdating;

  // Redirect if configuration not found in edit mode
  useEffect(() => {
    if (isEditMode && !isLoadingConfig && !configuration) {
      navigate('/configurations');
    }
  }, [isEditMode, isLoadingConfig, configuration, navigate]);

  const handleSubmit = async (data: StrategyConfigCreateData) => {
    try {
      if (isEditMode && configuration) {
        await updateConfiguration({
          id: configuration.id,
          data: {
            name: data.name,
            description: data.description,
            parameters: data.parameters,
          },
        });
      } else {
        await createConfiguration(data);
      }
      navigate('/configurations');
    } catch (error) {
      console.error('Failed to save configuration:', error);
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
      <Breadcrumbs />

      <Box sx={{ mb: 4 }}>
        <Typography variant="h4" gutterBottom>
          {isEditMode ? 'Edit Configuration' : 'Create New Configuration'}
        </Typography>
        <Typography variant="body1" color="text.secondary">
          {isEditMode
            ? 'Update your strategy configuration'
            : 'Create a reusable strategy configuration for backtesting and live trading'}
        </Typography>
      </Box>

      {isEditMode && !configuration && !isLoadingConfig && (
        <Alert severity="error" sx={{ mb: 3 }}>
          Configuration not found
        </Alert>
      )}

      <Paper elevation={2} sx={{ p: 4 }}>
        <ConfigurationForm
          initialData={
            configuration
              ? {
                  name: configuration.name,
                  strategy_type: configuration.strategy_type,
                  description: configuration.description,
                  parameters: configuration.parameters,
                }
              : undefined
          }
          onSubmit={handleSubmit}
          onCancel={handleCancel}
          isLoading={isLoading}
        />
      </Paper>
    </Container>
  );
};

export default ConfigurationFormPage;
