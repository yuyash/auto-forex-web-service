import React from 'react';
import {
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  FormHelperText,
  CircularProgress,
  Box,
  TextField,
  InputAdornment,
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import type { StrategyConfig } from '../../../types/configuration';
import {
  useStrategies,
  getStrategyDisplayName,
} from '../../../hooks/useStrategies';

interface ConfigurationSelectorProps {
  value: string | undefined;
  onChange: (value: string) => void;
  configurations: StrategyConfig[];
  isLoading?: boolean;
  error?: string;
  label?: string;
  required?: boolean;
  disabled?: boolean;
  helperText?: string;
  strategyTypeFilter?: string;
}

export const ConfigurationSelector: React.FC<ConfigurationSelectorProps> = ({
  value,
  onChange,
  configurations,
  isLoading = false,
  error,
  label = 'Strategy Configuration',
  required = false,
  disabled = false,
  helperText,
  strategyTypeFilter,
}) => {
  const [searchTerm, setSearchTerm] = React.useState('');
  const { strategies } = useStrategies();

  const filteredConfigurations = React.useMemo(() => {
    let filtered = configurations;

    // Filter by strategy type if provided
    if (strategyTypeFilter) {
      filtered = filtered.filter(
        (config) => config.strategy_type === strategyTypeFilter
      );
    }

    // Filter by search term
    if (searchTerm) {
      const lowerSearch = searchTerm.toLowerCase();
      filtered = filtered.filter(
        (config) =>
          config.name.toLowerCase().includes(lowerSearch) ||
          config.strategy_type.toLowerCase().includes(lowerSearch) ||
          config.description?.toLowerCase().includes(lowerSearch)
      );
    }

    return filtered;
  }, [configurations, searchTerm, strategyTypeFilter]);

  const selectedConfig = configurations.find((c) => c.id === value);

  return (
    <FormControl
      fullWidth
      error={!!error}
      required={required}
      disabled={disabled}
    >
      <InputLabel id="configuration-selector-label">{label}</InputLabel>
      <Select
        labelId="configuration-selector-label"
        id="configuration-selector"
        value={value || ''}
        label={label}
        onChange={(e) => {
          const val = e.target.value;
          if (typeof val === 'string' && val !== '') {
            onChange(val);
          }
        }}
        MenuProps={{
          PaperProps: {
            style: {
              maxHeight: 400,
            },
          },
        }}
      >
        {/* Search field in dropdown */}
        <Box
          sx={{
            px: 2,
            py: 1,
            position: 'sticky',
            top: 0,
            bgcolor: 'background.paper',
            zIndex: 1,
          }}
        >
          <TextField
            size="small"
            placeholder="Search configurations..."
            value={searchTerm}
            onChange={(e) => {
              e.stopPropagation();
              setSearchTerm(e.target.value);
            }}
            onClick={(e) => e.stopPropagation()}
            onKeyDown={(e) => e.stopPropagation()}
            fullWidth
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon fontSize="small" />
                </InputAdornment>
              ),
            }}
          />
        </Box>

        {isLoading ? (
          <MenuItem disabled>
            <CircularProgress size={20} sx={{ mr: 1 }} />
            Loading configurations...
          </MenuItem>
        ) : filteredConfigurations.length === 0 ? (
          <MenuItem disabled>
            {searchTerm
              ? 'No configurations found'
              : 'No configurations available'}
          </MenuItem>
        ) : (
          filteredConfigurations.map((config) => (
            <MenuItem key={config.id} value={config.id}>
              <Box>
                <Box sx={{ fontWeight: 500 }}>{config.name}</Box>
                <Box sx={{ fontSize: '0.875rem', color: 'text.secondary' }}>
                  {getStrategyDisplayName(strategies, config.strategy_type)}
                  {config.description &&
                    ` • ${config.description.substring(0, 50)}${config.description.length > 50 ? '...' : ''}`}
                </Box>
              </Box>
            </MenuItem>
          ))
        )}
      </Select>
      {error && <FormHelperText>{error}</FormHelperText>}
      {!error && helperText && <FormHelperText>{helperText}</FormHelperText>}
      {selectedConfig && !error && !helperText && (
        <FormHelperText>
          Strategy:{' '}
          {getStrategyDisplayName(strategies, selectedConfig.strategy_type)}
          {selectedConfig.is_in_use && ' • Currently in use'}
        </FormHelperText>
      )}
    </FormControl>
  );
};
