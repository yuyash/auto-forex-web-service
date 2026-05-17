import { useMemo, useState } from 'react';
import type { InitialPositionFilter } from '../../../hooks/useTaskPositions';

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const POSITION_ID_PREFIX_PATTERN = /^[0-9a-f-]{4,}$/i;

function toIsoDateTime(value: string): string | undefined {
  return value ? new Date(value).toISOString() : undefined;
}

export function useTaskPositionFilters() {
  const [cycleIdFilter, setCycleIdFilter] = useState('');
  const [positionIdFilter, setPositionIdFilter] = useState('');
  const [initialPositionFilter, setInitialPositionFilter] =
    useState<InitialPositionFilter>('all');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');

  const normalizedCycleId = cycleIdFilter.trim();
  const hasCycleIdFilter = normalizedCycleId.length > 0;
  const isCycleIdFilterValid =
    !hasCycleIdFilter || UUID_PATTERN.test(normalizedCycleId);
  const effectiveCycleId = isCycleIdFilterValid ? normalizedCycleId : '';

  const normalizedPositionId = positionIdFilter.trim();
  const hasPositionIdFilter = normalizedPositionId.length > 0;
  const isPositionIdFilterValid =
    !hasPositionIdFilter ||
    POSITION_ID_PREFIX_PATTERN.test(normalizedPositionId);
  const effectivePositionId =
    hasPositionIdFilter && isPositionIdFilterValid ? normalizedPositionId : '';

  const rangeFrom = useMemo(() => toIsoDateTime(dateFrom), [dateFrom]);
  const rangeTo = useMemo(() => toIsoDateTime(dateTo), [dateTo]);

  return {
    cycleIdFilter,
    setCycleIdFilter,
    hasCycleIdFilter,
    isCycleIdFilterValid,
    effectiveCycleId,
    positionIdFilter,
    setPositionIdFilter,
    hasPositionIdFilter,
    isPositionIdFilterValid,
    effectivePositionId,
    initialPositionFilter,
    setInitialPositionFilter,
    dateFrom,
    setDateFrom,
    dateTo,
    setDateTo,
    rangeFrom,
    rangeTo,
  };
}
