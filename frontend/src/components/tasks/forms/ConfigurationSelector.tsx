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
import {
  useConfiguration,
  useConfigurations,
} from '../../../hooks/useConfigurations';
import {
  useStrategies,
  getStrategyDisplayName,
} from '../../../hooks/useStrategies';

interface ConfigurationSelectorProps {
  value: string | undefined;
  onChange: (value: string) => void;
  error?: string;
  label?: string;
  required?: boolean;
  disabled?: boolean;
  helperText?: string;
  strategyTypeFilter?: string;
  allowEmptySelection?: boolean;
  emptySelectionLabel?: string;
}

export const ConfigurationSelector: React.FC<ConfigurationSelectorProps> = ({
  value,
  onChange,
  error,
  label = 'Strategy Configuration',
  required = false,
  disabled = false,
  helperText,
  strategyTypeFilter,
  allowEmptySelection = false,
  emptySelectionLabel = 'All configurations',
}) => {
  const [searchTerm, setSearchTerm] = React.useState('');
  const { strategies } = useStrategies();
  const { data: configurationsData, isLoading } = useConfigurations({
    page: 1,
    page_size: 50,
    search: searchTerm || undefined,
    strategy_type: strategyTypeFilter,
  });
  const { data: selectedConfiguration } = useConfiguration(value || undefined);

  const filteredConfigurations = React.useMemo(() => {
    const configurations = configurationsData?.results ?? [];
    if (
      value &&
      selectedConfiguration &&
      !configurations.some((config) => config.id === value)
    ) {
      return [selectedConfiguration, ...configurations];
    }
    return configurations;
  }, [configurationsData?.results, selectedConfiguration, value]);

  const selectedConfig =
    filteredConfigurations.find((config) => config.id === value) ??
    selectedConfiguration;

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
          if (typeof val === 'string') {
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

        {allowEmptySelection && (
          <MenuItem value="">{emptySelectionLabel}</MenuItem>
        )}

        {/* Hidden MenuItem to keep the selected value visible while configurations are loading */}
        {value &&
          !isLoading &&
          !filteredConfigurations.some((c) => c.id === value) && (
            <MenuItem value={value} sx={{ display: 'none' }}>
              {selectedConfig?.name || 'Loading...'}
            </MenuItem>
          )}

        {isLoading ? (
          [
            value ? (
              <MenuItem
                key="selected-loading-value"
                value={value}
                sx={{ display: 'none' }}
              >
                {selectedConfig?.name || 'Loading...'}
              </MenuItem>
            ) : null,
            <MenuItem key="loading-state" disabled>
              <CircularProgress size={20} sx={{ mr: 1 }} />
              Loading configurations...
            </MenuItem>,
          ]
        ) : filteredConfigurations.length === 0 ? (
          <MenuItem disabled>
            {searchTerm
              ? 'No configurations found'
              : allowEmptySelection
                ? 'Type to search configurations'
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
