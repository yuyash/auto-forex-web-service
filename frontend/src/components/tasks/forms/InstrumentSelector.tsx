import React from 'react';
import {
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  ListItemText,
  FormHelperText,
  Box,
  TextField,
  InputAdornment,
} from '@mui/material';
import type { SelectChangeEvent } from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';

interface InstrumentSelectorProps {
  value: string;
  onChange: (value: string) => void;
  availableInstrument?: string[];
  label?: string;
  required?: boolean;
  disabled?: boolean;
  error?: string;
  helperText?: string;
}

// Default forex instrument options
const DEFAULT_INSTRUMENT = [
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

const formatInstrumentLabel = (instrument: string) =>
  instrument.replace('_', '/');

export const InstrumentSelector: React.FC<InstrumentSelectorProps> = ({
  value,
  onChange,
  availableInstrument = DEFAULT_INSTRUMENT,
  label = 'Instrument',
  required = false,
  disabled = false,
  error,
  helperText,
}) => {
  const [searchTerm, setSearchTerm] = React.useState('');

  const filteredInstrument = React.useMemo(() => {
    if (!searchTerm) return availableInstrument;
    const lowerSearch = searchTerm.toLowerCase();
    return availableInstrument.filter((instrument) =>
      instrument.toLowerCase().includes(lowerSearch)
    );
  }, [availableInstrument, searchTerm]);

  const handleChange = (event: SelectChangeEvent<string>) => {
    const newValue = event.target.value as string;
    onChange(newValue);
  };

  const validationError = React.useMemo(() => {
    if (required && !value) {
      return 'Instrument is required';
    }
    return null;
  }, [value, required]);

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
        value={value}
        onChange={handleChange}
        label={label}
        renderValue={(selected) =>
          selected ? formatInstrumentLabel(selected as string) : ''
        }
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
            placeholder="Search instrument..."
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

        {filteredInstrument.length === 0 ? (
          <MenuItem disabled>No instrument found</MenuItem>
        ) : (
          filteredInstrument.map((instrument) => {
            // Only USD_JPY is enabled for now
            const isEnabled = instrument === 'USD_JPY';
            return (
              <MenuItem
                key={instrument}
                value={instrument}
                disabled={!isEnabled}
                sx={{
                  opacity: isEnabled ? 1 : 0.5,
                }}
              >
                <ListItemText
                  primary={instrument}
                  secondary={!isEnabled ? 'Coming soon' : undefined}
                />
              </MenuItem>
            );
          })
        )}
      </Select>
      {displayError && <FormHelperText>{displayError}</FormHelperText>}
      {!displayError && helperText && (
        <FormHelperText>{helperText}</FormHelperText>
      )}
    </FormControl>
  );
};
