import { useState } from 'react';
import {
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Alert,
  Box,
  Typography,
  Card,
  CardContent,
  CardActionArea,
  Grid,
  Chip,
  type SelectChangeEvent,
} from '@mui/material';
import { useTranslation } from 'react-i18next';
import type { Strategy } from '../../types/strategy';

interface StrategySelectorProps {
  strategies: Strategy[];
  selectedStrategy: string;
  onStrategyChange: (strategyId: string) => void;
  disabled?: boolean;
  loading?: boolean;
  variant?: 'dropdown' | 'cards';
}

const StrategySelector = ({
  strategies,
  selectedStrategy,
  onStrategyChange,
  disabled = false,
  loading = false,
  variant = 'dropdown',
}: StrategySelectorProps) => {
  const { t } = useTranslation('strategy');
  const [hoveredCard, setHoveredCard] = useState<string | null>(null);

  const handleSelectChange = (event: SelectChangeEvent<string>) => {
    onStrategyChange(event.target.value);
  };

  const handleCardClick = (strategyId: string) => {
    if (!disabled) {
      onStrategyChange(strategyId);
    }
  };

  const selectedStrategyData = strategies.find(
    (s) => s.id === selectedStrategy
  );

  if (loading) {
    return (
      <Box sx={{ p: 2 }}>
        <Typography variant="body2" color="text.secondary">
          Loading strategies...
        </Typography>
      </Box>
    );
  }

  if (strategies.length === 0) {
    return (
      <Alert severity="info">
        No strategies available. Please contact your administrator.
      </Alert>
    );
  }

  if (variant === 'cards') {
    return (
      <Box>
        <Typography variant="h6" gutterBottom>
          {t('selectStrategy')}
        </Typography>
        <Grid container spacing={2}>
          {strategies.map((strategy) => {
            const isSelected = strategy.id === selectedStrategy;
            const isHovered = strategy.id === hoveredCard;

            return (
              <Grid size={{ xs: 12, sm: 6, md: 4 }} key={strategy.id}>
                <Card
                  sx={{
                    height: '100%',
                    border: isSelected ? 2 : 1,
                    borderColor: isSelected ? 'primary.main' : 'divider',
                    transition: 'all 0.2s ease-in-out',
                    transform: isHovered ? 'translateY(-4px)' : 'none',
                    boxShadow: isHovered ? 4 : 1,
                    opacity: disabled ? 0.6 : 1,
                    cursor: disabled ? 'not-allowed' : 'pointer',
                  }}
                  onMouseEnter={() => !disabled && setHoveredCard(strategy.id)}
                  onMouseLeave={() => setHoveredCard(null)}
                >
                  <CardActionArea
                    onClick={() => handleCardClick(strategy.id)}
                    disabled={disabled}
                    sx={{ height: '100%' }}
                  >
                    <CardContent>
                      <Box
                        display="flex"
                        justifyContent="space-between"
                        alignItems="flex-start"
                        mb={1}
                      >
                        <Typography variant="h6" component="div">
                          {strategy.config_schema?.display_name ||
                            strategy.name}
                        </Typography>
                        {isSelected && (
                          <Chip label="Selected" color="primary" size="small" />
                        )}
                      </Box>
                      <Typography
                        variant="body2"
                        color="text.secondary"
                        sx={{
                          display: '-webkit-box',
                          WebkitLineClamp: 3,
                          WebkitBoxOrient: 'vertical',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          minHeight: '3.6em',
                        }}
                      >
                        {strategy.description}
                      </Typography>
                      <Box mt={2}>
                        <Typography
                          variant="caption"
                          color="text.secondary"
                          sx={{ fontFamily: 'monospace' }}
                        >
                          {strategy.class_name}
                        </Typography>
                      </Box>
                    </CardContent>
                  </CardActionArea>
                </Card>
              </Grid>
            );
          })}
        </Grid>

        {selectedStrategyData && (
          <Alert severity="info" sx={{ mt: 3 }}>
            <Typography variant="subtitle2" gutterBottom>
              {selectedStrategyData.config_schema?.display_name ||
                selectedStrategyData.name}
            </Typography>
            <Typography variant="body2">
              {selectedStrategyData.description}
            </Typography>
          </Alert>
        )}
      </Box>
    );
  }

  // Default dropdown variant
  return (
    <Box>
      <FormControl fullWidth>
        <InputLabel>{t('selectStrategy')}</InputLabel>
        <Select
          value={selectedStrategy}
          label={t('selectStrategy')}
          onChange={handleSelectChange}
          disabled={disabled || loading}
        >
          {strategies.map((strategy) => (
            <MenuItem key={strategy.id} value={strategy.id}>
              <Box>
                <Typography variant="body1">
                  {strategy.config_schema?.display_name || strategy.name}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {strategy.class_name}
                </Typography>
              </Box>
            </MenuItem>
          ))}
        </Select>
      </FormControl>

      {selectedStrategyData && (
        <Alert severity="info" sx={{ mt: 2 }}>
          <Typography variant="subtitle2" gutterBottom>
            {selectedStrategyData.config_schema?.display_name ||
              selectedStrategyData.name}
          </Typography>
          <Typography variant="body2">
            {selectedStrategyData.description}
          </Typography>
        </Alert>
      )}
    </Box>
  );
};

export default StrategySelector;
