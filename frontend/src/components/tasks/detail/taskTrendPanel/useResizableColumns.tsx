import { useCallback, useRef, useState } from 'react';
import { Box } from '@mui/material';

type WidthStateSetter = React.Dispatch<
  React.SetStateAction<Record<string, number>>
>;

export function useResizableColumns(initialWidths: Record<string, number>) {
  const [colWidths, setColWidths] = useState(initialWidths);
  const resizeRef = useRef<{
    col: string;
    startX: number;
    startW: number;
    setter: WidthStateSetter;
  } | null>(null);

  const handleResizeStart = useCallback(
    (
      e: React.MouseEvent | React.TouchEvent,
      col: string,
      widths: Record<string, number>,
      setter: WidthStateSetter
    ) => {
      e.preventDefault();
      e.stopPropagation();
      const clientX = 'touches' in e ? e.touches[0].clientX : e.clientX;
      resizeRef.current = {
        col,
        startX: clientX,
        startW: widths[col] ?? 100,
        setter,
      };

      const onMove = (ev: MouseEvent | TouchEvent) => {
        if (!resizeRef.current) return;
        const moveX =
          'touches' in ev ? ev.touches[0].clientX : (ev as MouseEvent).clientX;
        const diff = moveX - resizeRef.current.startX;
        const width = Math.max(40, resizeRef.current.startW + diff);
        resizeRef.current.setter((prev) => ({
          ...prev,
          [resizeRef.current!.col]: width,
        }));
      };

      const onEnd = () => {
        resizeRef.current = null;
        document.removeEventListener('mousemove', onMove);
        document.removeEventListener('mouseup', onEnd);
        document.removeEventListener('touchmove', onMove);
        document.removeEventListener('touchend', onEnd);
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
      };

      document.body.style.cursor = 'col-resize';
      document.body.style.userSelect = 'none';
      document.addEventListener('mousemove', onMove);
      document.addEventListener('mouseup', onEnd);
      document.addEventListener('touchmove', onMove, { passive: false });
      document.addEventListener('touchend', onEnd);
    },
    []
  );

  const createResizeHandle = useCallback(
    (
      col: string,
      widths: Record<string, number> = colWidths,
      setter: WidthStateSetter = setColWidths
    ) => (
      <Box
        onMouseDown={(e) => handleResizeStart(e, col, widths, setter)}
        onTouchStart={(e) => handleResizeStart(e, col, widths, setter)}
        sx={{
          position: 'absolute',
          right: 0,
          top: 0,
          bottom: 0,
          width: 4,
          cursor: 'col-resize',
          '&:hover': { backgroundColor: 'primary.main', opacity: 0.4 },
        }}
      />
    ),
    [colWidths, handleResizeStart]
  );

  return {
    colWidths,
    setColWidths,
    createResizeHandle,
  };
}
