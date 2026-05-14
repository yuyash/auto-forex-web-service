import {
  type GranularityOption,
  type TickDataPoint,
  type TickDataRange,
} from '../services/api/market';
import type {
  InstrumentMetadata,
  InstrumentsResponse,
} from '../types/instrument';
import {
  createFirstTickQuery,
  createSupportedGranularitiesQuery,
  createSupportedInstrumentsQuery,
  createTickDataRangeQuery,
} from './miscQueries';
import { mapQueryStateFields, useSimpleQueryState } from './useTaskCollections';
import {
  buildInstrumentMetadataMap,
  normalizeInstrumentName,
} from '../utils/instruments';

const FALLBACK_INSTRUMENTS = [
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

const FALLBACK_GRANULARITIES: GranularityOption[] = [
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

const FALLBACK_INSTRUMENT_METADATA =
  buildInstrumentMetadataMap(FALLBACK_INSTRUMENTS);

function metadataForInstruments(
  instruments: string[],
  apiMetadata?: Record<string, InstrumentMetadata>
): Record<string, InstrumentMetadata> {
  if (!apiMetadata) {
    return buildInstrumentMetadataMap(instruments);
  }
  return {
    ...buildInstrumentMetadataMap(instruments),
    ...Object.fromEntries(
      Object.entries(apiMetadata).map(([instrument, metadata]) => [
        normalizeInstrumentName(instrument),
        metadata,
      ])
    ),
  };
}

/**
 * Hook to fetch supported currency pairs from backend
 */
export const useSupportedInstruments = () => {
  const query = useSimpleQueryState(createSupportedInstrumentsQuery());

  return mapQueryStateFields(
    query,
    (data: InstrumentsResponse | null, state) => {
      const instruments = data?.instruments ?? FALLBACK_INSTRUMENTS;
      return {
        instruments,
        metadata: data
          ? metadataForInstruments(instruments, data.metadata)
          : FALLBACK_INSTRUMENT_METADATA,
        source: data?.source ?? null,
        error: state.error instanceof Error ? state.error.message : null,
        usingFallback: !state.isLoading && !data && !!state.error,
      };
    }
  );
};

/**
 * Hook to fetch supported granularities from backend
 */
export const useSupportedGranularities = () => {
  const query = useSimpleQueryState(createSupportedGranularitiesQuery());

  return mapQueryStateFields(query, (data, state) => ({
    granularities: data ?? FALLBACK_GRANULARITIES,
    error: state.error instanceof Error ? state.error.message : null,
    usingFallback: !state.isLoading && !data && !!state.error,
  }));
};

/**
 * Hook to fetch the available tick data range for a given instrument.
 */
export const useTickDataRange = (instrument?: string) => {
  const query = useSimpleQueryState(createTickDataRangeQuery(instrument));

  return mapQueryStateFields(query, (data, state) => ({
    dataRange: (data as TickDataRange | undefined) ?? null,
    error: state.error instanceof Error ? state.error.message : null,
  }));
};

/**
 * Hook to fetch the first tick in a backtest period for a given instrument.
 */
export const useFirstTick = (
  instrument?: string,
  fromTime?: string,
  toTime?: string,
  options?: { enabled?: boolean }
) => {
  const query = useSimpleQueryState(
    createFirstTickQuery(instrument, fromTime, toTime, options)
  );

  return mapQueryStateFields(query, (data, state) => ({
    firstTick: (data as TickDataPoint | null | undefined) ?? null,
    error: state.error instanceof Error ? state.error.message : null,
  }));
};
