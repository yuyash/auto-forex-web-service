/**
 * Adaptive Time Scale Plugin for lightweight-charts
 *
 * Replaces the default time axis labels with custom two-line rendering.
 * Also draws vertical grid lines aligned with the labels so they always match.
 *
 * The built-in vertical grid lines should be DISABLED when using this plugin
 * (grid.vertLines.visible = false) because the plugin draws its own.
 */

import type { CanvasRenderingTarget2D } from 'fancy-canvas';
import type {
  ISeriesPrimitive,
  SeriesAttachedParameter,
  Time,
  IPrimitivePaneView,
  IPrimitivePaneRenderer,
} from 'lightweight-charts';
import { formatInTimeZone } from 'date-fns-tz';

// ── Types ───────────────────────────────────────────────────────────

export interface AdaptiveTimeScaleOptions {
  timezone: string;
}

interface TickLabel {
  x: number;
  line1: string;
  line2: string;
}

const WIDE_RANGE_SEC = 30 * 86_400;

type TickInterval = {
  approxSec: number;
  isAligned: (date: Date, timezone: string) => boolean;
  format: (
    date: Date,
    timezone: string,
    previousDateStr: string
  ) => { line1: string; line2: string; nextDateStr: string };
};

const getTzNumber = (date: Date, timezone: string, token: string): number =>
  Number(formatInTimeZone(date, timezone, token));

const formatIntradayLabel = (
  date: Date,
  timezone: string,
  previousDateStr: string
) => {
  const dateStr = formatInTimeZone(date, timezone, 'MM/dd');
  const timeStr = formatInTimeZone(date, timezone, 'HH:mm');
  if (dateStr !== previousDateStr) {
    return { line1: dateStr, line2: timeStr, nextDateStr: dateStr };
  }
  return { line1: '', line2: timeStr, nextDateStr: dateStr };
};

const formatDateOnlyLabel = (
  date: Date,
  timezone: string,
  previousDateStr: string
) => {
  const dateStr = formatInTimeZone(date, timezone, 'MM/dd');
  return {
    line1: dateStr,
    line2: previousDateStr === dateStr ? '' : '',
    nextDateStr: dateStr,
  };
};

const formatMonthLabel = (date: Date, timezone: string) => {
  const monthStr = formatInTimeZone(date, timezone, 'yyyy/MM');
  return { line1: monthStr, line2: '', nextDateStr: monthStr };
};

const formatYearLabel = (date: Date, timezone: string) => {
  const yearStr = formatInTimeZone(date, timezone, 'yyyy');
  return { line1: yearStr, line2: '', nextDateStr: yearStr };
};

// ── Time Axis Renderer (labels in the bottom time-axis pane) ────────

class TimeAxisRenderer implements IPrimitivePaneRenderer {
  private _labels: TickLabel[];
  private _textColor: string;

  constructor(labels: TickLabel[], textColor: string) {
    this._labels = labels;
    this._textColor = textColor;
  }

  draw(target: CanvasRenderingTarget2D): void {
    target.useBitmapCoordinateSpace((scope) => {
      const ctx = scope.context;
      const ratio = scope.horizontalPixelRatio;
      const vRatio = scope.verticalPixelRatio;
      const h = scope.bitmapSize.height;

      const fontSize = Math.round(11 * ratio);
      ctx.font = `${fontSize}px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`;
      ctx.fillStyle = this._textColor;
      ctx.textAlign = 'center';

      for (const label of this._labels) {
        const bx = Math.round(label.x * ratio);

        if (label.line1 && label.line2) {
          const lineGap = Math.round(2 * vRatio);
          const totalH = fontSize * 2 + lineGap;
          const topY = Math.round((h - totalH) / 2) + fontSize;
          ctx.textBaseline = 'alphabetic';
          ctx.fillText(label.line1, bx, topY);
          ctx.fillText(label.line2, bx, topY + fontSize + lineGap);
        } else {
          const text = label.line1 || label.line2;
          if (!text) continue;
          ctx.textBaseline = 'middle';
          ctx.fillText(text, bx, Math.round(h / 2));
        }
      }
    });
  }
}

// ── Grid Line Renderer (vertical lines in the main chart pane) ──────

class GridLineRenderer implements IPrimitivePaneRenderer {
  private _xPositions: number[];
  private _color: string;

  constructor(xPositions: number[], color: string) {
    this._xPositions = xPositions;
    this._color = color;
  }

  draw(target: CanvasRenderingTarget2D): void {
    target.useBitmapCoordinateSpace((scope) => {
      const ctx = scope.context;
      const ratio = scope.horizontalPixelRatio;
      const h = scope.bitmapSize.height;

      ctx.strokeStyle = this._color;
      ctx.lineWidth = Math.max(1, ratio);

      for (const x of this._xPositions) {
        const bx = Math.round(x * ratio);
        ctx.beginPath();
        ctx.moveTo(bx, 0);
        ctx.lineTo(bx, h);
        ctx.stroke();
      }
    });
  }
}

// ── PaneViews ───────────────────────────────────────────────────────

class TimeAxisPaneView implements IPrimitivePaneView {
  private _source: AdaptiveTimeScale;
  constructor(source: AdaptiveTimeScale) {
    this._source = source;
  }
  zOrder(): 'bottom' {
    return 'bottom';
  }
  renderer(): IPrimitivePaneRenderer | null {
    return this._source.buildTimeAxisRenderer();
  }
}

class GridPaneView implements IPrimitivePaneView {
  private _source: AdaptiveTimeScale;
  constructor(source: AdaptiveTimeScale) {
    this._source = source;
  }
  zOrder(): 'bottom' {
    return 'bottom';
  }
  renderer(): IPrimitivePaneRenderer | null {
    return this._source.buildGridRenderer();
  }
}

// ── Primitive ───────────────────────────────────────────────────────

export class AdaptiveTimeScale implements ISeriesPrimitive<Time> {
  private _param: SeriesAttachedParameter<Time> | null = null;
  private _timeAxisViews: TimeAxisPaneView[];
  private _gridViews: GridPaneView[];
  private _timezone: string;
  private _textColor: string;
  private _gridColor: string;

  constructor(
    options: AdaptiveTimeScaleOptions,
    textColor = '#334155',
    gridColor = '#e2e8f0'
  ) {
    this._timezone = options.timezone;
    this._textColor = textColor;
    this._gridColor = gridColor;
    this._timeAxisViews = [new TimeAxisPaneView(this)];
    this._gridViews = [new GridPaneView(this)];
  }

  attached(param: SeriesAttachedParameter<Time>): void {
    this._param = param;
  }

  detached(): void {
    this._param = null;
  }

  setTimezone(tz: string): void {
    this._timezone = tz;
    this._param?.requestUpdate();
  }

  setTextColor(color: string): void {
    this._textColor = color;
    this._param?.requestUpdate();
  }

  /** Labels on the time axis pane */
  timeAxisPaneViews(): readonly IPrimitivePaneView[] {
    return this._timeAxisViews;
  }

  /** Vertical grid lines on the main chart pane */
  paneViews(): readonly IPrimitivePaneView[] {
    return this._gridViews;
  }

  updateAllViews(): void {
    // Coordinate computation happens in renderer() calls (real-time).
  }

  // ── Shared label computation (called at render time) ──────────────

  private static readonly TICK_INTERVALS: TickInterval[] = [
    {
      approxSec: 60,
      isAligned: () => true,
      format: formatIntradayLabel,
    },
    {
      approxSec: 300,
      isAligned: (date, tz) => getTzNumber(date, tz, 'm') % 5 === 0,
      format: formatIntradayLabel,
    },
    {
      approxSec: 600,
      isAligned: (date, tz) => getTzNumber(date, tz, 'm') % 10 === 0,
      format: formatIntradayLabel,
    },
    {
      approxSec: 900,
      isAligned: (date, tz) => getTzNumber(date, tz, 'm') % 15 === 0,
      format: formatIntradayLabel,
    },
    {
      approxSec: 1800,
      isAligned: (date, tz) => getTzNumber(date, tz, 'm') % 30 === 0,
      format: formatIntradayLabel,
    },
    {
      approxSec: 3600,
      isAligned: (date, tz) => getTzNumber(date, tz, 'm') === 0,
      format: formatIntradayLabel,
    },
    {
      approxSec: 7200,
      isAligned: (date, tz) =>
        getTzNumber(date, tz, 'm') === 0 &&
        getTzNumber(date, tz, 'H') % 2 === 0,
      format: formatIntradayLabel,
    },
    {
      approxSec: 14400,
      isAligned: (date, tz) =>
        getTzNumber(date, tz, 'm') === 0 &&
        getTzNumber(date, tz, 'H') % 4 === 0,
      format: formatIntradayLabel,
    },
    {
      approxSec: 28800,
      isAligned: (date, tz) =>
        getTzNumber(date, tz, 'm') === 0 &&
        getTzNumber(date, tz, 'H') % 8 === 0,
      format: formatIntradayLabel,
    },
    {
      approxSec: 43200,
      isAligned: (date, tz) =>
        getTzNumber(date, tz, 'm') === 0 &&
        getTzNumber(date, tz, 'H') % 12 === 0,
      format: formatIntradayLabel,
    },
    {
      approxSec: 86400,
      isAligned: (date, tz) =>
        getTzNumber(date, tz, 'H') === 0 && getTzNumber(date, tz, 'm') === 0,
      format: formatDateOnlyLabel,
    },
    {
      approxSec: 172800,
      isAligned: (date, tz) =>
        getTzNumber(date, tz, 'H') === 0 &&
        getTzNumber(date, tz, 'm') === 0 &&
        getTzNumber(date, tz, 'd') % 2 === 1,
      format: formatDateOnlyLabel,
    },
    {
      approxSec: 604800,
      isAligned: (date, tz) =>
        getTzNumber(date, tz, 'H') === 0 &&
        getTzNumber(date, tz, 'm') === 0 &&
        getTzNumber(date, tz, 'i') === 1,
      format: formatDateOnlyLabel,
    },
    {
      approxSec: 2629746,
      isAligned: (date, tz) =>
        getTzNumber(date, tz, 'H') === 0 &&
        getTzNumber(date, tz, 'm') === 0 &&
        getTzNumber(date, tz, 'd') === 1,
      format: formatMonthLabel,
    },
    {
      approxSec: 2 * 2629746,
      isAligned: (date, tz) =>
        getTzNumber(date, tz, 'H') === 0 &&
        getTzNumber(date, tz, 'm') === 0 &&
        getTzNumber(date, tz, 'd') === 1 &&
        (getTzNumber(date, tz, 'M') - 1) % 2 === 0,
      format: formatMonthLabel,
    },
    {
      approxSec: 3 * 2629746,
      isAligned: (date, tz) =>
        getTzNumber(date, tz, 'H') === 0 &&
        getTzNumber(date, tz, 'm') === 0 &&
        getTzNumber(date, tz, 'd') === 1 &&
        (getTzNumber(date, tz, 'M') - 1) % 3 === 0,
      format: formatMonthLabel,
    },
    {
      approxSec: 6 * 2629746,
      isAligned: (date, tz) =>
        getTzNumber(date, tz, 'H') === 0 &&
        getTzNumber(date, tz, 'm') === 0 &&
        getTzNumber(date, tz, 'd') === 1 &&
        (getTzNumber(date, tz, 'M') - 1) % 6 === 0,
      format: formatMonthLabel,
    },
    {
      approxSec: 31556952,
      isAligned: (date, tz) =>
        getTzNumber(date, tz, 'H') === 0 &&
        getTzNumber(date, tz, 'm') === 0 &&
        getTzNumber(date, tz, 'd') === 1 &&
        getTzNumber(date, tz, 'M') === 1,
      format: formatYearLabel,
    },
  ];

  private _computeLabels(): TickLabel[] | null {
    if (!this._param) return null;

    const chart = this._param.chart;
    const timeScale = chart.timeScale();
    const tz = this._timezone;

    const visibleRange = timeScale.getVisibleRange();
    if (!visibleRange) return null;

    // Get the time boundaries in seconds
    const fromSec =
      typeof visibleRange.from === 'number'
        ? visibleRange.from
        : new Date(visibleRange.from as string).getTime() / 1000;
    const toSec =
      typeof visibleRange.to === 'number'
        ? visibleRange.to
        : new Date(visibleRange.to as string).getTime() / 1000;
    if (toSec <= fromSec) return null;

    const spanSec = toSec - fromSec;
    const isWideRange = spanSec >= WIDE_RANGE_SEC;

    const series = this._param.series;
    const data = series.data();
    if (!data || data.length === 0) return null;

    const logicalRange = timeScale.getVisibleLogicalRange();
    if (!logicalRange) return null;

    const si = Math.max(0, Math.floor(logicalRange.from));
    const ei = Math.min(data.length - 1, Math.ceil(logicalRange.to));
    if (si >= ei) return null;

    const visiblePoints: Array<{ x: number; sec: number }> = [];
    for (const point of data.slice(si, ei + 1)) {
      const x = timeScale.timeToCoordinate(point.time);
      if (x === null) continue;
      const sec =
        typeof point.time === 'number'
          ? point.time
          : new Date(point.time as string).getTime() / 1000;
      visiblePoints.push({ x: Number(x), sec });
    }
    if (visiblePoints.length === 0) return null;

    // Determine how many labels fit and pick a nice interval
    const pxWidth = Math.abs(
      visiblePoints[visiblePoints.length - 1].x - visiblePoints[0].x
    );
    const labelWidth = isWideRange ? 28 : 32;
    const maxLabels = Math.max(2, Math.floor(pxWidth / labelWidth));
    const idealIntervalSec = spanSec / maxLabels;

    // Pick the smallest allowed interval >= idealIntervalSec.
    let interval =
      AdaptiveTimeScale.TICK_INTERVALS[
        AdaptiveTimeScale.TICK_INTERVALS.length - 1
      ];
    for (const candidate of AdaptiveTimeScale.TICK_INTERVALS) {
      if (candidate.approxSec >= idealIntervalSec) {
        interval = candidate;
        break;
      }
    }

    const labels: TickLabel[] = [];
    let lastDateStr = '';
    let lastLabelSec = Number.NEGATIVE_INFINITY;

    for (const point of visiblePoints) {
      if (point.sec < fromSec || point.sec > toSec) continue;
      const date = new Date(point.sec * 1000);
      if (!interval.isAligned(date, tz)) continue;
      if (labels.length > 0 && point.sec - lastLabelSec < interval.approxSec) {
        continue;
      }

      const x = point.x;
      const formatted = interval.format(date, tz, lastDateStr);
      labels.push({ x, line1: formatted.line1, line2: formatted.line2 });
      lastDateStr = formatted.nextDateStr;
      lastLabelSec = point.sec;
    }

    return labels;
  }

  /** Called by TimeAxisPaneView.renderer() */
  buildTimeAxisRenderer(): IPrimitivePaneRenderer | null {
    const labels = this._computeLabels();
    if (!labels || labels.length === 0) return null;
    return new TimeAxisRenderer(labels, this._textColor);
  }

  /** Called by GridPaneView.renderer() */
  buildGridRenderer(): IPrimitivePaneRenderer | null {
    const labels = this._computeLabels();
    if (!labels || labels.length === 0) return null;
    return new GridLineRenderer(
      labels.map((l) => l.x),
      this._gridColor
    );
  }
}

// ── Exported helpers for chart components ────────────────────────────

export function createSuppressedTickMarkFormatter(): () => string {
  return () => '';
}

export function createTooltipTimeFormatter(opts: {
  timezone: string;
}): (time: number) => string {
  return (time: number) => {
    const date = new Date(time * 1000);
    return formatInTimeZone(date, opts.timezone, 'yyyy-MM-dd HH:mm:ss');
  };
}
