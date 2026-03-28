import { useCallback, useMemo, useRef, useState } from 'react';
import type React from 'react';
import {
  readRawStoredValue,
  writeRawStoredValue,
} from '../../../../utils/persistentState';

interface UseTaskTrendPanelStateParams {
  taskType: string;
  taskId: string | number;
  executionRunId?: string;
}

export function useTaskTrendPanelState({
  taskType,
  taskId,
  executionRunId,
}: UseTaskTrendPanelStateParams) {
  const [granularity, setGranularity] = useState<string>('M1');
  const [selectedTradeId, setSelectedTradeId] = useState<string | null>(null);
  const [pollingIntervalMs, setPollingIntervalMs] = useState(10_000);
  const [chartWarningState, setChartWarningState] = useState<{
    contextKey: string;
    message: string | null;
  }>({
    contextKey: '',
    message: null,
  });
  const [autoFollow, setAutoFollow] = useState(true);
  const [selectedPosId, setSelectedPosId] = useState<string | null>(null);
  const [highlightedTradeIds, setHighlightedTradeIds] = useState<Set<string>>(
    new Set()
  );
  const [markersVisible, setMarkersVisible] = useState(false);
  const chartClickedRef = useRef(false);
  const selectedPosRowRef = useRef<HTMLTableRowElement | null>(null);

  const minChartHeight = 200;
  const chartHeightStorageKey = 'replay-chart-height';
  const [chartHeight, setChartHeight] = useState(() => {
    const saved = readRawStoredValue(chartHeightStorageKey);
    if (saved) {
      const parsed = parseInt(saved, 10);
      if (Number.isFinite(parsed) && parsed >= minChartHeight) {
        return parsed;
      }
    }
    return 400;
  });
  const dragRef = useRef<{ startY: number; startHeight: number } | null>(null);

  const chartWarningContextKey = useMemo(
    () => `${taskType}:${taskId}:${executionRunId ?? 'none'}:${granularity}`,
    [executionRunId, granularity, taskId, taskType]
  );

  const chartWarning = useMemo(
    () =>
      chartWarningState.contextKey === chartWarningContextKey
        ? chartWarningState.message
        : null,
    [chartWarningContextKey, chartWarningState]
  );

  const reportChartWarning = useCallback(
    (message: string | null) => {
      setChartWarningState((prev) => {
        if (
          prev.contextKey === chartWarningContextKey &&
          prev.message === message
        ) {
          return prev;
        }
        return { contextKey: chartWarningContextKey, message };
      });
    },
    [chartWarningContextKey]
  );

  const handleSeparatorMouseDown = useCallback(
    (event: React.MouseEvent | React.TouchEvent) => {
      event.preventDefault();
      const clientY =
        'touches' in event ? event.touches[0].clientY : event.clientY;
      dragRef.current = { startY: clientY, startHeight: chartHeight };

      const onMove = (moveEvent: MouseEvent | TouchEvent) => {
        if (!dragRef.current) {
          return;
        }
        const moveY =
          'touches' in moveEvent
            ? moveEvent.touches[0].clientY
            : moveEvent.clientY;
        const diff = moveY - dragRef.current.startY;
        const nextHeight = Math.min(
          window.innerHeight,
          Math.max(minChartHeight, dragRef.current.startHeight + diff)
        );
        setChartHeight(nextHeight);
      };

      const onEnd = () => {
        dragRef.current = null;
        document.removeEventListener('mousemove', onMove);
        document.removeEventListener('mouseup', onEnd);
        document.removeEventListener('touchmove', onMove);
        document.removeEventListener('touchend', onEnd);
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
        setChartHeight((height) => {
          writeRawStoredValue(chartHeightStorageKey, String(height));
          return height;
        });
      };

      document.body.style.cursor = 'row-resize';
      document.body.style.userSelect = 'none';
      document.addEventListener('mousemove', onMove);
      document.addEventListener('mouseup', onEnd);
      document.addEventListener('touchmove', onMove, { passive: false });
      document.addEventListener('touchend', onEnd);
    },
    [chartHeight]
  );

  return {
    granularity,
    setGranularity,
    selectedTradeId,
    setSelectedTradeId,
    pollingIntervalMs,
    setPollingIntervalMs,
    autoFollow,
    setAutoFollow,
    selectedPosId,
    setSelectedPosId,
    highlightedTradeIds,
    setHighlightedTradeIds,
    markersVisible,
    setMarkersVisible,
    chartClickedRef,
    selectedPosRowRef,
    chartHeight,
    minChartHeight,
    handleSeparatorMouseDown,
    chartWarning,
    reportChartWarning,
  };
}
