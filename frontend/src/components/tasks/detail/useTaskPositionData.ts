import { useCallback, useMemo, useState } from 'react';

import {
  useTaskPositions,
  type InitialPositionFilter,
  type TaskPosition,
} from '../../../hooks/useTaskPositions';
import type { TaskType } from '../../../types/common';
import type { PositionViewMode } from './useTaskPositionViewMode';

export type SortOrder = 'asc' | 'desc';

type PositionStatus = 'open' | 'closed';
type PositionDirection = 'long' | 'short';

interface UseTaskPositionDataOptions {
  taskId: string | number;
  taskType: TaskType;
  executionRunId?: string;
  enableRealTimeUpdates: boolean;
  viewMode: PositionViewMode;
  effectiveCycleId: string;
  effectivePositionId: string;
  initialPositionFilter: InitialPositionFilter;
  rangeFrom?: string;
  rangeTo?: string;
}

interface PositionQueryState {
  positions: TaskPosition[];
  totalCount: number;
  isLoading: boolean;
  error: Error | null;
  refresh: () => Promise<unknown>;
}

interface PositionTableQuery extends PositionQueryState {
  page: number;
  setPage: (page: number) => void;
  rowsPerPage: number;
  setRowsPerPage: (rowsPerPage: number) => void;
}

const DEFAULT_SPLIT_ROWS_PER_PAGE = 10;
const DEFAULT_ALL_ROWS_PER_PAGE = 25;

const toOrdering = (field: string, order: SortOrder): string =>
  order === 'desc' ? `-${field}` : field;

export function useTaskPositionData({
  taskId,
  taskType,
  executionRunId,
  enableRealTimeUpdates,
  viewMode,
  effectiveCycleId,
  effectivePositionId,
  initialPositionFilter,
  rangeFrom,
  rangeTo,
}: UseTaskPositionDataOptions) {
  const [closedLongPage, setClosedLongPage] = useState(0);
  const [closedShortPage, setClosedShortPage] = useState(0);
  const [openLongPage, setOpenLongPage] = useState(0);
  const [openShortPage, setOpenShortPage] = useState(0);
  const [closedLongRpp, setClosedLongRpp] = useState(
    DEFAULT_SPLIT_ROWS_PER_PAGE
  );
  const [closedShortRpp, setClosedShortRpp] = useState(
    DEFAULT_SPLIT_ROWS_PER_PAGE
  );
  const [openLongRpp, setOpenLongRpp] = useState(DEFAULT_SPLIT_ROWS_PER_PAGE);
  const [openShortRpp, setOpenShortRpp] = useState(DEFAULT_SPLIT_ROWS_PER_PAGE);

  const [longPage, setLongPage] = useState(0);
  const [shortPage, setShortPage] = useState(0);
  const [longRpp, setLongRpp] = useState(DEFAULT_SPLIT_ROWS_PER_PAGE);
  const [shortRpp, setShortRpp] = useState(DEFAULT_SPLIT_ROWS_PER_PAGE);

  const [allPage, setAllPage] = useState(0);
  const [allRpp, setAllRpp] = useState(DEFAULT_ALL_ROWS_PER_PAGE);
  const [sortField, setSortField] = useState('entry_time');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');

  const ordering = toOrdering(sortField, sortOrder);
  const commonFilters = {
    taskId,
    taskType,
    executionRunId,
    cycleId: effectiveCycleId || undefined,
    positionId: effectivePositionId || undefined,
    initialPositionFilter,
    rangeFrom,
    rangeTo,
    ordering,
  };

  const closedLong = useTaskPositionQuery({
    ...commonFilters,
    status: 'closed',
    direction: 'long',
    page: closedLongPage,
    rowsPerPage: closedLongRpp,
    setPage: setClosedLongPage,
    setRowsPerPage: setClosedLongRpp,
    enableRealTimeUpdates: enableRealTimeUpdates && viewMode === 'byStatus',
  });
  const closedShort = useTaskPositionQuery({
    ...commonFilters,
    status: 'closed',
    direction: 'short',
    page: closedShortPage,
    rowsPerPage: closedShortRpp,
    setPage: setClosedShortPage,
    setRowsPerPage: setClosedShortRpp,
    enableRealTimeUpdates: enableRealTimeUpdates && viewMode === 'byStatus',
  });
  const openLong = useTaskPositionQuery({
    ...commonFilters,
    status: 'open',
    direction: 'long',
    page: openLongPage,
    rowsPerPage: openLongRpp,
    setPage: setOpenLongPage,
    setRowsPerPage: setOpenLongRpp,
    enableRealTimeUpdates: enableRealTimeUpdates && viewMode === 'byStatus',
  });
  const openShort = useTaskPositionQuery({
    ...commonFilters,
    status: 'open',
    direction: 'short',
    page: openShortPage,
    rowsPerPage: openShortRpp,
    setPage: setOpenShortPage,
    setRowsPerPage: setOpenShortRpp,
    enableRealTimeUpdates: enableRealTimeUpdates && viewMode === 'byStatus',
  });

  const long = useTaskPositionQuery({
    ...commonFilters,
    direction: 'long',
    page: longPage,
    rowsPerPage: longRpp,
    setPage: setLongPage,
    setRowsPerPage: setLongRpp,
    enableRealTimeUpdates: enableRealTimeUpdates && viewMode === 'byDirection',
  });
  const short = useTaskPositionQuery({
    ...commonFilters,
    direction: 'short',
    page: shortPage,
    rowsPerPage: shortRpp,
    setPage: setShortPage,
    setRowsPerPage: setShortRpp,
    enableRealTimeUpdates: enableRealTimeUpdates && viewMode === 'byDirection',
  });
  const all = useTaskPositionQuery({
    ...commonFilters,
    page: allPage,
    rowsPerPage: allRpp,
    setPage: setAllPage,
    setRowsPerPage: setAllRpp,
    enableRealTimeUpdates: enableRealTimeUpdates && viewMode === 'all',
  });

  const isLoading =
    viewMode === 'byStatus'
      ? closedLong.isLoading ||
        closedShort.isLoading ||
        openLong.isLoading ||
        openShort.isLoading
      : viewMode === 'byDirection'
        ? long.isLoading || short.isLoading
        : all.isLoading;
  const error =
    viewMode === 'byStatus'
      ? closedLong.error ||
        closedShort.error ||
        openLong.error ||
        openShort.error
      : viewMode === 'byDirection'
        ? long.error || short.error
        : all.error;

  const resetPages = useCallback(() => {
    setClosedLongPage(0);
    setClosedShortPage(0);
    setOpenLongPage(0);
    setOpenShortPage(0);
    setLongPage(0);
    setShortPage(0);
    setAllPage(0);
  }, []);

  const handleSortChange = useCallback(
    (field: string, order: SortOrder) => {
      setSortField(field);
      setSortOrder(order);
      resetPages();
    },
    [resetPages]
  );

  return useMemo(
    () => ({
      closedLong,
      closedShort,
      openLong,
      openShort,
      long,
      short,
      all,
      isLoading,
      error,
      sortField,
      sortOrder,
      handleSortChange,
      resetPages,
    }),
    [
      closedLong,
      closedShort,
      openLong,
      openShort,
      long,
      short,
      all,
      isLoading,
      error,
      sortField,
      sortOrder,
      handleSortChange,
      resetPages,
    ]
  );
}

interface UseTaskPositionQueryOptions {
  taskId: string | number;
  taskType: TaskType;
  executionRunId?: string;
  status?: PositionStatus;
  direction?: PositionDirection;
  page: number;
  rowsPerPage: number;
  setPage: (page: number) => void;
  setRowsPerPage: (rowsPerPage: number) => void;
  cycleId?: string;
  positionId?: string;
  initialPositionFilter: InitialPositionFilter;
  rangeFrom?: string;
  rangeTo?: string;
  ordering: string;
  enableRealTimeUpdates: boolean;
}

function useTaskPositionQuery({
  taskId,
  taskType,
  executionRunId,
  status,
  direction,
  page,
  rowsPerPage,
  setPage,
  setRowsPerPage,
  cycleId,
  positionId,
  initialPositionFilter,
  rangeFrom,
  rangeTo,
  ordering,
  enableRealTimeUpdates,
}: UseTaskPositionQueryOptions): PositionTableQuery {
  const query = useTaskPositions({
    taskId,
    taskType,
    executionRunId,
    status,
    direction,
    page: page + 1,
    pageSize: rowsPerPage,
    cycleId,
    positionId,
    initialPositionFilter,
    rangeFrom,
    rangeTo,
    ordering,
    enableRealTimeUpdates,
  });

  return {
    positions: query.positions,
    totalCount: query.totalCount,
    isLoading: query.isLoading,
    error: query.error,
    refresh: query.refresh,
    page,
    setPage,
    rowsPerPage,
    setRowsPerPage,
  };
}
