import React from 'react';
import { useTranslation } from 'react-i18next';
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
  label,
  required = false,
  disabled = false,
  error,
  helperText,
}) => {
  const { t } = useTranslation(['common']);
  const [searchTerm, setSearchTerm] = React.useState('');
  const resolvedLabel = label ?? t('common:labels.instrument');

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
      return t('common:validation.instrumentRequired');
    }
    return null;
  }, [value, required, t]);

  const displayError = error || validationError;

  return (
    <FormControl
      fullWidth
      error={!!displayError}
      required={required}
      disabled={disabled}
    >
      <InputLabel id="instrument-selector-label">{resolvedLabel}</InputLabel>
      <Select
        labelId="instrument-selector-label"
        id="instrument-selector"
        value={value}
        onChange={handleChange}
        label={resolvedLabel}
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
            placeholder={t('common:instrument.searchPlaceholder')}
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
          <MenuItem disabled>
            {t('common:instrument.noInstrumentFound')}
          </MenuItem>
        ) : (
          filteredInstrument.map((instrument) => (
            <MenuItem key={instrument} value={instrument}>
              <ListItemText primary={instrument} />
            </MenuItem>
          ))
        )}
      </Select>
      {displayError && <FormHelperText>{displayError}</FormHelperText>}
      {!displayError && helperText && (
        <FormHelperText>{helperText}</FormHelperText>
      )}
    </FormControl>
  );
};
