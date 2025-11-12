import { useState } from 'react';
import {
  Box,
  Button,
  TextField,
  Typography,
  CircularProgress,
  Card,
  CardContent,
  Chip,
} from '@mui/material';

interface ParametersFormProps {
  strategyType: string;
  strategyName: string;
  initialParameters: Record<string, unknown>;
  onSubmit: (parameters: Record<string, unknown>) => Promise<void>;
  onCancel: () => void;
  isLoading?: boolean;
}

const ParametersForm = ({
  strategyType,
  strategyName,
  initialParameters,
  onSubmit,
  onCancel,
  isLoading = false,
}: ParametersFormProps) => {
  const [parameters, setParameters] =
    useState<Record<string, unknown>>(initialParameters);

  const handleParameterChange = (key: string, value: unknown) => {
    setParameters((prev) => ({ ...prev, [key]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await onSubmit(parameters);
  };

  return (
    <form onSubmit={handleSubmit}>
      <Card variant="outlined" sx={{ mb: 3, bgcolor: 'grey.50' }}>
        <CardContent>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 1 }}>
            <Typography variant="subtitle2" color="text.secondary">
              Configuration:
            </Typography>
            <Typography variant="body1" fontWeight={600}>
              {strategyName}
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <Typography variant="subtitle2" color="text.secondary">
              Strategy Type:
            </Typography>
            <Chip
              label={strategyType
                .replace(/_/g, ' ')
                .replace(/\b\w/g, (l) => l.toUpperCase())}
              size="small"
              color="primary"
              variant="outlined"
            />
          </Box>
        </CardContent>
      </Card>

      <Typography variant="h6" gutterBottom>
        Strategy Parameters
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        Update the parameters for your strategy configuration
      </Typography>

      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        {Object.entries(parameters).map(([key, value]) => (
          <TextField
            key={key}
            fullWidth
            label={key
              .replace(/_/g, ' ')
              .replace(/\b\w/g, (l) => l.toUpperCase())}
            value={value as string | number}
            onChange={(e) => {
              const newValue =
                typeof value === 'number'
                  ? Number(e.target.value)
                  : e.target.value;
              handleParameterChange(key, newValue);
            }}
            type={typeof value === 'number' ? 'number' : 'text'}
            disabled={isLoading}
          />
        ))}
      </Box>

      <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 2, mt: 4 }}>
        <Button onClick={onCancel} disabled={isLoading}>
          Cancel
        </Button>
        <Button
          type="submit"
          variant="contained"
          disabled={isLoading}
          startIcon={isLoading ? <CircularProgress size={20} /> : null}
        >
          {isLoading ? 'Saving...' : 'Save Parameters'}
        </Button>
      </Box>
    </form>
  );
};

export default ParametersForm;
