import { useCallback } from 'react';

interface UseTaskTrendTableStateParams {
  setTradePage: (value: number) => void;
  setLongPosPage: (value: number) => void;
  setShortPosPage: (value: number) => void;
  setTradeRowsPerPage: (value: number) => void;
  setLongPosRowsPerPage: (value: number) => void;
  setShortPosRowsPerPage: (value: number) => void;
  setTradeConfigOpen: (value: boolean) => void;
  setLongPosConfigOpen: (value: boolean) => void;
  setShortPosConfigOpen: (value: boolean) => void;
}

export function useTaskTrendTableState({
  setTradePage,
  setLongPosPage,
  setShortPosPage,
  setTradeRowsPerPage,
  setLongPosRowsPerPage,
  setShortPosRowsPerPage,
  setTradeConfigOpen,
  setLongPosConfigOpen,
  setShortPosConfigOpen,
}: UseTaskTrendTableStateParams) {
  const handleRowsPerPageChange = useCallback(
    (event: { target: { value: string } }) => {
      const newValue = parseInt(event.target.value, 10);
      setTradeRowsPerPage(newValue);
      setLongPosRowsPerPage(newValue);
      setShortPosRowsPerPage(newValue);
      setTradePage(0);
      setLongPosPage(0);
      setShortPosPage(0);
    },
    [
      setLongPosPage,
      setLongPosRowsPerPage,
      setShortPosPage,
      setShortPosRowsPerPage,
      setTradePage,
      setTradeRowsPerPage,
    ]
  );

  return {
    openTradeColumns: () => setTradeConfigOpen(true),
    closeTradeColumns: () => setTradeConfigOpen(false),
    openLongColumns: () => setLongPosConfigOpen(true),
    closeLongColumns: () => setLongPosConfigOpen(false),
    openShortColumns: () => setShortPosConfigOpen(true),
    closeShortColumns: () => setShortPosConfigOpen(false),
    handleRowsPerPageChange,
  };
}
