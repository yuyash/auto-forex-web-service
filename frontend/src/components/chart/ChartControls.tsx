import {
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Button,
} from '@mui/material';
import RestartAltIcon from '@mui/icons-material/RestartAlt';
import type { SelectChangeEvent } from '@mui/material';
import type { Granularity } from '../../types/chart';

interface ChartControlsProps {
  instrument: string;
  granularity: Granularity;
  onInstrumentChange: (instrument: string) => void;
  onGranularityChange: (granularity: Granularity) => void;
  onResetView?: () => void;
  showResetButton?: boolean;
}

// Common currency pairs for forex trading
const CURRENCY_PAIRS = [
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
  'AUD_JPY',
  'GBP_CHF',
  'EUR_AUD',
  'EUR_CAD',
];

// OANDA granularities
const GRANULARITIES: { value: Granularity; label: string }[] = [
  { value: 'S5', label: '5 Seconds' },
  { value: 'S10', label: '10 Seconds' },
  { value: 'S15', label: '15 Seconds' },
  { value: 'S30', label: '30 Seconds' },
  { value: 'M1', label: '1 Minute' },
  { value: 'M2', label: '2 Minutes' },
  { value: 'M4', label: '4 Minutes' },
  { value: 'M5', label: '5 Minutes' },
  { value: 'M10', label: '10 Minutes' },
  { value: 'M15', label: '15 Minutes' },
  { value: 'M30', label: '30 Minutes' },
  { value: 'H1', label: '1 Hour' },
  { value: 'H2', label: '2 Hours' },
  { value: 'H3', label: '3 Hours' },
  { value: 'H4', label: '4 Hours' },
  { value: 'H6', label: '6 Hours' },
  { value: 'H8', label: '8 Hours' },
  { value: 'H12', label: '12 Hours' },
  { value: 'D', label: 'Daily' },
  { value: 'W', label: 'Weekly' },
  { value: 'M', label: 'Monthly' },
];

const ChartControls = ({
  instrument,
  granularity,
  onInstrumentChange,
  onGranularityChange,
  onResetView,
  showResetButton = false,
}: ChartControlsProps) => {
  const handleInstrumentChange = (event: SelectChangeEvent<string>) => {
    onInstrumentChange(event.target.value);
  };

  const handleGranularityChange = (event: SelectChangeEvent<string>) => {
    onGranularityChange(event.target.value as Granularity);
  };

  return (
    <>
      {/* Currency Pair Selector */}
      <FormControl sx={{ minWidth: 140, height: 32 }} size="small">
        <InputLabel id="instrument-label" sx={{ fontSize: '0.85rem' }}>
          Currency Pair
        </InputLabel>
        <Select
          labelId="instrument-label"
          id="instrument-select"
          value={instrument}
          label="Currency Pair"
          onChange={handleInstrumentChange}
          sx={{ height: 32, fontSize: '0.85rem' }}
        >
          {CURRENCY_PAIRS.map((pair) => (
            <MenuItem key={pair} value={pair} sx={{ fontSize: '0.85rem' }}>
              {pair.replace('_', '/')}
            </MenuItem>
          ))}
        </Select>
      </FormControl>

      {/* Granularity Selector */}
      <FormControl sx={{ minWidth: 120, height: 32 }} size="small">
        <InputLabel id="granularity-label" sx={{ fontSize: '0.85rem' }}>
          Timeframe
        </InputLabel>
        <Select
          labelId="granularity-label"
          id="granularity-select"
          value={granularity}
          label="Timeframe"
          onChange={handleGranularityChange}
          sx={{ height: 32, fontSize: '0.85rem' }}
        >
          {GRANULARITIES.map((gran) => (
            <MenuItem
              key={gran.value}
              value={gran.value}
              sx={{ fontSize: '0.85rem' }}
            >
              {gran.label}
            </MenuItem>
          ))}
        </Select>
      </FormControl>

      {/* Reset View Button */}
      {showResetButton && onResetView && (
        <Button
          variant="outlined"
          size="small"
          onClick={onResetView}
          startIcon={<RestartAltIcon sx={{ fontSize: '1rem' }} />}
          sx={{ height: 32, fontSize: '0.85rem', px: 1.5 }}
        >
          Reset View
        </Button>
      )}
    </>
  );
};

export default ChartControls;
