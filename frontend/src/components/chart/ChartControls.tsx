import {
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Button,
  CircularProgress,
} from '@mui/material';
import RestartAltIcon from '@mui/icons-material/RestartAlt';
import UpdateIcon from '@mui/icons-material/Update';
import type { SelectChangeEvent } from '@mui/material';
import type { Granularity } from '../../types/chart';
import {
  useSupportedInstruments,
  useSupportedGranularities,
} from '../../hooks/useMarketConfig';

interface ChartControlsProps {
  instrument: string;
  granularity: Granularity;
  onInstrumentChange: (instrument: string) => void;
  onGranularityChange: (granularity: Granularity) => void;
  onResetView?: () => void;
  onUpdateView?: () => void;
  showResetButton?: boolean;
  showUpdateButton?: boolean;
}

const ChartControls = ({
  instrument,
  granularity,
  onInstrumentChange,
  onGranularityChange,
  onResetView,
  onUpdateView,
  showResetButton = false,
  showUpdateButton = false,
}: ChartControlsProps) => {
  // Fetch supported instruments and granularities from backend
  const { instruments: currencyPairs, isLoading: instrumentsLoading } =
    useSupportedInstruments();
  const { granularities, isLoading: granularitiesLoading } =
    useSupportedGranularities();
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
          disabled={instrumentsLoading}
          sx={{ height: 32, fontSize: '0.85rem' }}
          startAdornment={
            instrumentsLoading ? (
              <CircularProgress size={16} sx={{ ml: 1 }} />
            ) : null
          }
        >
          {currencyPairs.map((pair) => (
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
          disabled={granularitiesLoading}
          sx={{ height: 32, fontSize: '0.85rem' }}
          startAdornment={
            granularitiesLoading ? (
              <CircularProgress size={16} sx={{ ml: 1 }} />
            ) : null
          }
        >
          {granularities.map((gran) => (
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
          Reset
        </Button>
      )}

      {/* Update View Button */}
      {showUpdateButton && onUpdateView && (
        <Button
          variant="contained"
          size="small"
          onClick={onUpdateView}
          startIcon={<UpdateIcon sx={{ fontSize: '1rem' }} />}
          sx={{ height: 32, fontSize: '0.85rem', px: 1.5 }}
        >
          Update
        </Button>
      )}
    </>
  );
};

export default ChartControls;
