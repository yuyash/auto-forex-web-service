import type { RefObject } from 'react';

interface MarketChartTooltipProps {
  isDark: boolean;
  tooltipRef: RefObject<HTMLDivElement | null>;
}

export function MarketChartTooltip({
  isDark,
  tooltipRef,
}: MarketChartTooltipProps) {
  return (
    <div
      ref={tooltipRef}
      style={{
        position: 'absolute',
        top: 8,
        left: 8,
        zIndex: 2,
        display: 'none',
        fontSize: '11px',
        fontFamily:
          '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
        color: isDark ? '#ffffff' : '#334155',
        backgroundColor: isDark
          ? 'rgba(30,34,45,0.9)'
          : 'rgba(255,255,255,0.85)',
        padding: '4px 8px',
        borderRadius: '4px',
        pointerEvents: 'none',
        whiteSpace: 'normal',
        maxWidth: 'calc(100% - 16px)',
        overflow: 'hidden',
        textOverflow: 'ellipsis',
      }}
    />
  );
}
