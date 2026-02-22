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

// ── Helpers ─────────────────────────────────────────────────────────

const isMidnightInTz = (date: Date, tz: string): boolean => {
  const hh = formatInTimeZone(date, tz, 'HH');
  const mm = formatInTimeZone(date, tz, 'mm');
  return hh === '00' && mm === '00';
};

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

  // Nice tick intervals in seconds, from small to large
  private static readonly TICK_INTERVALS = [
    60, // 1 min
    120, // 2 min
    300, // 5 min
    600, // 10 min
    900, // 15 min
    1800, // 30 min
    3600, // 1 h
    7200, // 2 h
    14400, // 4 h
    21600, // 6 h
    43200, // 12 h
    86400, // 1 day
    172800, // 2 days
    604800, // 1 week
    2592000, // 30 days
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

    // We need two known data-point coordinates to build a time→pixel mapping.
    // Use the first and last visible data points.
    const series = this._param.series;
    const data = series.data();
    if (!data || data.length === 0) return null;

    const logicalRange = timeScale.getVisibleLogicalRange();
    if (!logicalRange) return null;

    const si = Math.max(0, Math.floor(logicalRange.from));
    const ei = Math.min(data.length - 1, Math.ceil(logicalRange.to));
    if (si >= ei) return null;

    const ptA = data[si];
    const ptB = data[ei];
    const xA = timeScale.timeToCoordinate(ptA.time);
    const xB = timeScale.timeToCoordinate(ptB.time);
    if (xA === null || xB === null) return null;

    const secA =
      typeof ptA.time === 'number'
        ? ptA.time
        : new Date(ptA.time as string).getTime() / 1000;
    const secB =
      typeof ptB.time === 'number'
        ? ptB.time
        : new Date(ptB.time as string).getTime() / 1000;
    if (secB <= secA) return null;

    // Linear interpolation: time (seconds) → pixel x
    const secToX = (sec: number): number => {
      return xA + ((sec - secA) / (secB - secA)) * (xB - xA);
    };

    // Determine how many labels fit and pick a nice interval
    const pxWidth = Math.abs(xB - xA);
    const labelWidth = isWideRange ? 55 : 65;
    const maxLabels = Math.max(2, Math.floor(pxWidth / labelWidth));
    const idealIntervalSec = spanSec / maxLabels;

    // Pick the smallest nice interval >= idealIntervalSec
    let intervalSec =
      AdaptiveTimeScale.TICK_INTERVALS[
        AdaptiveTimeScale.TICK_INTERVALS.length - 1
      ];
    for (const candidate of AdaptiveTimeScale.TICK_INTERVALS) {
      if (candidate >= idealIntervalSec) {
        intervalSec = candidate;
        break;
      }
    }

    // Round fromSec up to the next multiple of intervalSec (in UTC)
    const firstTick = Math.ceil(fromSec / intervalSec) * intervalSec;

    // Generate tick times
    const labels: TickLabel[] = [];
    let lastDateStr = '';
    // When interval is >= 1 day, every tick lands on a day boundary
    // so showing "00:00" is redundant — use date-only labels.
    const dateOnly = isWideRange || intervalSec >= 86400;

    for (let tick = firstTick; tick <= toSec; tick += intervalSec) {
      const x = secToX(tick);
      const date = new Date(tick * 1000);
      const dateStr = formatInTimeZone(date, tz, 'MM/dd');
      const timeStr = formatInTimeZone(date, tz, 'HH:mm');
      const midnight = isMidnightInTz(date, tz);

      if (dateOnly) {
        // Date only (single line)
        labels.push({ x, line1: dateStr, line2: '' });
      } else if (midnight || dateStr !== lastDateStr) {
        // Major tick: date + time (two lines)
        labels.push({ x, line1: dateStr, line2: timeStr });
      } else {
        // Minor tick: time only
        labels.push({ x, line1: '', line2: timeStr });
      }
      lastDateStr = dateStr;
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
