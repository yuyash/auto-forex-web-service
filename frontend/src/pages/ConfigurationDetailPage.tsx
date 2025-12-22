import { useMemo } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Container,
  Divider,
  Paper,
  Typography,
} from '@mui/material';
import { Edit as EditIcon } from '@mui/icons-material';
import { Breadcrumbs } from '../components/common';
import { useConfiguration } from '../hooks/useConfigurations';
import { useStrategies, getStrategyDisplayName } from '../hooks/useStrategies';

function formatDate(dateString?: string) {
  if (!dateString) return '';
  return new Date(dateString).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return '';
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

export default function ConfigurationDetailPage() {
  const { id } = useParams<{ id: string }>();
  const configId = useMemo(() => Number(id), [id]);
  const navigate = useNavigate();

  const { data: configuration, isLoading, error } = useConfiguration(configId);
  const { strategies } = useStrategies();

  return (
    <Container maxWidth="md" sx={{ mt: 4, mb: 4, px: 3 }}>
      <Breadcrumbs />

      {isLoading && (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
          <CircularProgress />
        </Box>
      )}

      {!isLoading && error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          Failed to load configuration
        </Alert>
      )}

      {!isLoading && !error && !configuration && (
        <Alert severity="error" sx={{ mb: 3 }}>
          Configuration not found
        </Alert>
      )}

      {!isLoading && !error && configuration && (
        <>
          <Box
            sx={{
              mb: 3,
              display: 'flex',
              alignItems: 'flex-start',
              justifyContent: 'space-between',
              gap: 2,
              flexWrap: 'wrap',
            }}
          >
            <Box sx={{ minWidth: 0 }}>
              <Typography variant="h4" gutterBottom>
                {configuration.name}
              </Typography>
              <Typography variant="body1" color="text.secondary">
                Strategy configuration details
              </Typography>
            </Box>

            <Button
              variant="contained"
              startIcon={<EditIcon />}
              onClick={() =>
                navigate(`/configurations/${configuration.id}/edit`)
              }
            >
              Edit
            </Button>
          </Box>

          <Paper elevation={2} sx={{ p: 3 }}>
            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 2 }}>
              <Chip
                label={getStrategyDisplayName(
                  strategies,
                  configuration.strategy_type
                )}
                color="primary"
                size="small"
                variant="outlined"
              />
              <Chip
                label={`Created ${formatDate(configuration.created_at)}`}
                size="small"
                variant="outlined"
              />
              {configuration.is_in_use && (
                <Chip
                  label="In Use"
                  color="success"
                  size="small"
                  variant="filled"
                />
              )}
            </Box>

            {configuration.description && (
              <Box sx={{ mb: 2 }}>
                <Typography variant="subtitle2" gutterBottom>
                  Description
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  {configuration.description}
                </Typography>
              </Box>
            )}

            <Divider sx={{ my: 2 }} />

            <Typography variant="subtitle2" gutterBottom>
              Parameters
            </Typography>

            {Object.keys(configuration.parameters || {}).length === 0 ? (
              <Typography variant="body2" color="text.secondary">
                No parameters saved for this configuration.
              </Typography>
            ) : (
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                {Object.entries(configuration.parameters || {}).map(
                  ([key, value]) => (
                    <Box
                      key={key}
                      sx={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        gap: 2,
                      }}
                    >
                      <Typography variant="body2" sx={{ fontWeight: 600 }}>
                        {key}
                      </Typography>
                      <Typography
                        variant="body2"
                        color="text.secondary"
                        sx={{ textAlign: 'right', wordBreak: 'break-word' }}
                      >
                        {formatValue(value)}
                      </Typography>
                    </Box>
                  )
                )}
              </Box>
            )}
          </Paper>
        </>
      )}
    </Container>
  );
}
