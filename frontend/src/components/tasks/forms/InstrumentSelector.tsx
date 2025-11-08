import React from 'react';
import {
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Checkbox,
  ListItemText,
  FormHelperText,
  Chip,
  Box,
  TextField,
  InputAdornment,
} from '@mui/material';
import type { SelectChangeEvent } from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';

interface InstrumentSelectorProps {
  value: string[];
  onChange: (value: string[]) => void;
  availableInstruments?: string[];
  label?: string;
  required?: boolean;
  disabled?: boolean;
  error?: string;
  helperText?: string;
  maxSelections?: number;
}

// Default forex instruments
const DEFAULT_INSTRUMENTS = [
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
  'EUR_AUD',
  'EUR_CAD',
  'GBP_CHF',
  'GBP_AUD',
  'AUD_JPY',
  'AUD_NZD',
  'CAD_JPY',
  'CHF_JPY',
  'NZD_JPY',
];

export const InstrumentSelector: React.FC<InstrumentSelectorProps> = ({
  value,
  onChange,
  availableInstruments = DEFAULT_INSTRUMENTS,
  label = 'Instruments',
  required = false,
  disabled = false,
  error,
  helperText,
  maxSelections,
}) => {
  const [searchTerm, setSearchTerm] = React.useState('');

  const filteredInstruments = React.useMemo(() => {
    if (!searchTerm) return availableInstruments;
    const lowerSearch = searchTerm.toLowerCase();
    return availableInstruments.filter((instrument) =>
      instrument.toLowerCase().includes(lowerSearch)
    );
  }, [availableInstruments, searchTerm]);

  const handleChange = (event: SelectChangeEvent<string[]>) => {
    const newValue = event.target.value as string[];

    // Check max selections
    if (maxSelections && newValue.length > maxSelections) {
      return;
    }

    onChange(newValue);
  };

  const handleDelete = (instrumentToDelete: string) => {
    onChange(value.filter((instrument) => instrument !== instrumentToDelete));
  };

  const validationError = React.useMemo(() => {
    if (required && value.length === 0) {
      return 'At least one instrument is required';
    }
    if (maxSelections && value.length > maxSelections) {
      return `Maximum ${maxSelections} instrument${maxSelections > 1 ? 's' : ''} allowed`;
    }
    return null;
  }, [value, required, maxSelections]);

  const displayError = error || validationError;

  return (
    <FormControl
      fullWidth
      error={!!displayError}
      required={required}
      disabled={disabled}
    >
      <InputLabel id="instrument-selector-label">{label}</InputLabel>
      <Select
        labelId="instrument-selector-label"
        id="instrument-selector"
        multiple
        value={value}
        onChange={handleChange}
        label={label}
        renderValue={(selected) => (
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
            {selected.map((instrument) => (
              <Chip
                key={instrument}
                label={instrument}
                size="small"
                onDelete={() => handleDelete(instrument)}
                onMouseDown={(e) => e.stopPropagation()}
              />
            ))}
          </Box>
        )}
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
            placeholder="Search instruments..."
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

        {filteredInstruments.length === 0 ? (
          <MenuItem disabled>No instruments found</MenuItem>
        ) : (
          filteredInstruments.map((instrument) => (
            <MenuItem key={instrument} value={instrument}>
              <Checkbox checked={value.indexOf(instrument) > -1} />
              <ListItemText primary={instrument} />
            </MenuItem>
          ))
        )}
      </Select>
      {displayError && <FormHelperText>{displayError}</FormHelperText>}
      {!displayError && helperText && (
        <FormHelperText>{helperText}</FormHelperText>
      )}
      {!displayError && !helperText && value.length > 0 && (
        <FormHelperText>
          {value.length} instrument{value.length !== 1 ? 's' : ''} selected
          {maxSelections && ` (max ${maxSelections})`}
        </FormHelperText>
      )}
    </FormControl>
  );
};
