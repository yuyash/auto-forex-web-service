/**
 * MarketClosedHighlight — lightweight-charts series primitive plugin
 *
 * Draws semi-transparent rectangles over time gaps caused by market closures
 * (weekends / holidays). Attach to a candlestick series via attachPrimitive().
 */
import type { CanvasRenderingTarget2D } from 'fancy-canvas';
import type {
  ISeriesPrimitive,
  SeriesAttachedParameter,
  Time,
  IPrimitivePaneView,
  IPrimitivePaneRenderer,
} from 'lightweight-charts';

/** A single market-closed gap */
export interface ClosedGap {
  /** Timestamp (UTCTimestamp) of the last candle before the gap */
  from: number;
  /** Timestamp (UTCTimestamp) of the first candle after the gap */
  to: number;
  /** Human-readable label */
  label: string;
}

// ── Renderer ────────────────────────────────────────────────────────

class HighlightRenderer implements IPrimitivePaneRenderer {
  private _rects: { x1: number; x2: number; label: string }[];

  constructor(rects: { x1: number; x2: number; label: string }[]) {
    this._rects = rects;
  }

  draw(target: CanvasRenderingTarget2D): void {
    target.useBitmapCoordinateSpace((scope) => {
      const ctx = scope.context;
      const h = scope.bitmapSize.height;
      const ratio = scope.horizontalPixelRatio;

      for (const r of this._rects) {
        const x1 = Math.round(r.x1 * ratio);
        const x2 = Math.round(r.x2 * ratio);
        const width = x2 - x1;
        if (width <= 0) continue;

        // Semi-transparent background
        ctx.fillStyle = 'rgba(148, 163, 184, 0.12)';
        ctx.fillRect(x1, 0, width, h);

        // Dashed vertical borders
        ctx.strokeStyle = 'rgba(148, 163, 184, 0.35)';
        ctx.lineWidth = Math.max(1, ratio);
        ctx.setLineDash([4 * ratio, 4 * ratio]);
        ctx.beginPath();
        ctx.moveTo(x1, 0);
        ctx.lineTo(x1, h);
        ctx.moveTo(x2, 0);
        ctx.lineTo(x2, h);
        ctx.stroke();
        ctx.setLineDash([]);

        // Label
        const fontSize = Math.round(11 * ratio);
        ctx.font = `${fontSize}px sans-serif`;
        ctx.fillStyle = 'rgba(100, 116, 139, 0.7)';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';
        const cx = (x1 + x2) / 2;
        ctx.fillText(r.label, cx, 8 * ratio);
      }
    });
  }
}

// ── PaneView ────────────────────────────────────────────────────────

class HighlightPaneView implements IPrimitivePaneView {
  private _source: MarketClosedHighlight;

  constructor(source: MarketClosedHighlight) {
    this._source = source;
  }

  zOrder(): 'bottom' {
    return 'bottom';
  }

  renderer(): IPrimitivePaneRenderer | null {
    const param = this._source.getAttachedParams();
    if (!param) return null;

    const timeScale = param.chart.timeScale();
    const rects: { x1: number; x2: number; label: string }[] = [];

    for (const gap of this._source.getGaps()) {
      const x1 = timeScale.timeToCoordinate(gap.from as unknown as Time);
      const x2 = timeScale.timeToCoordinate(gap.to as unknown as Time);
      if (x1 === null || x2 === null) continue;
      rects.push({ x1, x2, label: gap.label });
    }

    if (rects.length === 0) return null;
    return new HighlightRenderer(rects);
  }
}

// ── Primitive ───────────────────────────────────────────────────────

export class MarketClosedHighlight implements ISeriesPrimitive<Time> {
  private _gaps: ClosedGap[] = [];
  private _paneViews: HighlightPaneView[];
  private _param: SeriesAttachedParameter<Time> | null = null;

  constructor() {
    this._paneViews = [new HighlightPaneView(this)];
  }

  attached(param: SeriesAttachedParameter<Time>): void {
    this._param = param;
  }

  detached(): void {
    this._param = null;
  }

  getAttachedParams() {
    return this._param;
  }

  getGaps() {
    return this._gaps;
  }

  /** Call this whenever candle data changes */
  setGaps(gaps: ClosedGap[]): void {
    this._gaps = gaps;
    this._param?.requestUpdate();
  }

  updateAllViews(): void {
    // paneViews re-read gaps on each render
  }

  paneViews(): readonly IPrimitivePaneView[] {
    return this._paneViews;
  }
}
