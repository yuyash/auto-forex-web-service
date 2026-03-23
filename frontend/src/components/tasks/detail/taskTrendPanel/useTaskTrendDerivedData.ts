import { useMemo } from 'react';
import {
  ALLOWED_GRANULARITIES,
  ALLOWED_VALUES,
  GRANULARITY_MINUTES,
  recommendGranularity,
} from './shared';
import type { TrendPosition } from './shared';

interface GranularityOption {
  value: string;
  label: string;
}

interface UseTaskTrendDerivedDataParams {
  fetchedPositions: TrendPosition[];
  granularities: GranularityOption[];
  instrument: string;
  startTime?: string;
  endTime?: string;
  currentTickPrice?: string | null;
}

export function useTaskTrendDerivedData({
  fetchedPositions,
  granularities,
  instrument,
  startTime,
  endTime,
  currentTickPrice,
}: UseTaskTrendDerivedDataParams) {
  const currentPrice =
    currentTickPrice != null ? parseFloat(currentTickPrice) : null;

  const allPositions = useMemo<TrendPosition[]>(() => {
    return [...fetchedPositions]
      .map((position) => ({
        ...position,
        _status: (position.is_open ? 'open' : 'closed') as 'open' | 'closed',
      }))
      .sort(
        (a, b) =>
          new Date(b.entry_time).getTime() - new Date(a.entry_time).getTime()
      );
  }, [fetchedPositions]);

  const longPositions = useMemo(
    () => allPositions.filter((position) => position.direction === 'long'),
    [allPositions]
  );
  const shortPositions = useMemo(
    () => allPositions.filter((position) => position.direction === 'short'),
    [allPositions]
  );

  const granularityOptions = useMemo(() => {
    if (granularities.length > 0) {
      return granularities.filter((option) => ALLOWED_VALUES.has(option.value));
    }
    return ALLOWED_GRANULARITIES;
  }, [granularities]);

  const recommendedGranularity = useMemo(() => {
    const availableValues = granularityOptions
      .map((option) => option.value)
      .filter((value) => !!GRANULARITY_MINUTES[value]);
    return recommendGranularity(startTime, endTime, availableValues);
  }, [endTime, granularityOptions, startTime]);

  const pnlCurrency = instrument?.includes('_')
    ? instrument.split('_')[1]
    : 'N/A';

  return {
    currentPrice,
    allPositions,
    longPositions,
    shortPositions,
    granularityOptions,
    recommendedGranularity,
    pnlCurrency,
  };
}
