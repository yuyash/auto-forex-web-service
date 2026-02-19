/**
 * SequencePositionLine — lightweight-charts series primitive plugin
 *
 * Draws a vertical line on the chart at the current backtest tick position,
 * with a dot marker at the intersection with the current price.
 * Uses the actual tick timestamp and price from the backend.
 */
import type { CanvasRenderingTarget2D } from 'fancy-canvas';
import type {
  ISeriesPrimitive,
  SeriesAttachedParameter,
  Time,
  IPrimitivePaneView,
  IPrimitivePaneRenderer,
} from 'lightweight-charts';

// ── Renderer ────────────────────────────────────────────────────────

class LineRenderer implements IPrimitivePaneRenderer {
  private _x: number;
  private _priceY: number | null;
  private _priceLabel: string;

  constructor(x: number, priceY: number | null, priceLabel: string) {
    this._x = x;
    this._priceY = priceY;
    this._priceLabel = priceLabel;
  }

  draw(target: CanvasRenderingTarget2D): void {
    target.useBitmapCoordinateSpace((scope) => {
      const ctx = scope.context;
      const h = scope.bitmapSize.height;
      const ratio = scope.horizontalPixelRatio;
      const vRatio = scope.verticalPixelRatio;
      const x = Math.round(this._x * ratio);

      // Vertical dashed line
      ctx.strokeStyle = 'rgba(59, 130, 246, 0.7)';
      ctx.lineWidth = Math.max(2, 2 * ratio);
      ctx.setLineDash([6 * ratio, 4 * ratio]);
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, h);
      ctx.stroke();
      ctx.setLineDash([]);

      // Price dot and label at intersection
      if (this._priceY !== null) {
        const py = Math.round(this._priceY * vRatio);

        // Dot
        const dotRadius = 5 * ratio;
        ctx.beginPath();
        ctx.arc(x, py, dotRadius, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(59, 130, 246, 1)';
        ctx.fill();
        ctx.strokeStyle = '#ffffff';
        ctx.lineWidth = Math.max(1.5, 1.5 * ratio);
        ctx.stroke();
      }

      // Top badge with price
      const fontSize = Math.round(11 * ratio);
      ctx.font = `bold ${fontSize}px sans-serif`;
      const text = this._priceLabel;
      const textWidth = ctx.measureText(text).width;
      const padX = 6 * ratio;
      const padY = 3 * ratio;
      const badgeW = textWidth + padX * 2;
      const badgeH = fontSize + padY * 2;
      const badgeX = x - badgeW / 2;
      const badgeY = 6 * ratio;

      // Badge background
      ctx.fillStyle = 'rgba(59, 130, 246, 0.9)';
      const r = 3 * ratio;
      ctx.beginPath();
      ctx.moveTo(badgeX + r, badgeY);
      ctx.lineTo(badgeX + badgeW - r, badgeY);
      ctx.quadraticCurveTo(
        badgeX + badgeW,
        badgeY,
        badgeX + badgeW,
        badgeY + r
      );
      ctx.lineTo(badgeX + badgeW, badgeY + badgeH - r);
      ctx.quadraticCurveTo(
        badgeX + badgeW,
        badgeY + badgeH,
        badgeX + badgeW - r,
        badgeY + badgeH
      );
      ctx.lineTo(badgeX + r, badgeY + badgeH);
      ctx.quadraticCurveTo(
        badgeX,
        badgeY + badgeH,
        badgeX,
        badgeY + badgeH - r
      );
      ctx.lineTo(badgeX, badgeY + r);
      ctx.quadraticCurveTo(badgeX, badgeY, badgeX + r, badgeY);
      ctx.closePath();
      ctx.fill();

      // Badge text
      ctx.fillStyle = '#ffffff';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'top';
      ctx.fillText(text, x, badgeY + padY);
    });
  }
}

// ── PaneView ────────────────────────────────────────────────────────

class LinePaneView implements IPrimitivePaneView {
  private _source: SequencePositionLine;

  constructor(source: SequencePositionLine) {
    this._source = source;
  }

  zOrder(): 'top' {
    return 'top';
  }

  renderer(): IPrimitivePaneRenderer | null {
    const param = this._source.getAttachedParams();
    if (!param) return null;

    const timestamp = this._source.getTimestamp();
    if (timestamp === null) return null;

    const timeScale = param.chart.timeScale();
    const width = timeScale.width();
    if (width <= 0) return null;

    // Try direct coordinate lookup
    let x = timeScale.timeToCoordinate(timestamp as unknown as Time);

    // Fallback: interpolate using two known data-point coordinates so the
    // line stays anchored to the correct time position even when the user
    // scrolls / zooms and the exact timestamp has no matching data point.
    if (x === null) {
      const series = param.series;
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

      const fraction = (timestamp - secA) / (secB - secA);
      // Allow rendering slightly outside visible area for smooth transitions
      if (fraction < -0.1 || fraction > 1.1) return null;

      x = (xA + fraction * (xB - xA)) as unknown as ReturnType<
        typeof timeScale.timeToCoordinate
      >;
    }

    // Convert price to y-coordinate
    let priceY: number | null = null;
    const price = this._source.getPrice();
    if (price !== null) {
      const series = param.series;
      const coord = series.priceToCoordinate(price);
      if (coord !== null) {
        priceY = coord as number;
      }
    }

    const priceLabel = this._source.getPriceLabel();
    return new LineRenderer(x as number, priceY, priceLabel);
  }
}

// ── Primitive ───────────────────────────────────────────────────────

export class SequencePositionLine implements ISeriesPrimitive<Time> {
  private _timestamp: number | null = null;
  private _price: number | null = null;
  private _priceLabel = '';
  private _paneViews: LinePaneView[];
  private _param: SeriesAttachedParameter<Time> | null = null;
  private _deferredUpdateId: ReturnType<typeof requestAnimationFrame> | null =
    null;

  constructor() {
    this._paneViews = [new LinePaneView(this)];
  }

  attached(param: SeriesAttachedParameter<Time>): void {
    this._param = param;
  }

  detached(): void {
    this._cancelDeferredUpdate();
    this._param = null;
  }

  getAttachedParams() {
    return this._param;
  }

  getTimestamp(): number | null {
    return this._timestamp;
  }

  getPrice(): number | null {
    return this._price;
  }

  getPriceLabel(): string {
    return this._priceLabel;
  }

  /**
   * Update the position using actual tick timestamp and price.
   * @param timestamp ISO string of the current tick
   * @param price Current mid price (or null if unavailable)
   */
  setPosition(timestamp: string, price: number | null): void {
    const ms = new Date(timestamp).getTime();
    if (!Number.isFinite(ms)) {
      this.clear();
      return;
    }

    this._timestamp = Math.floor(ms / 1000);
    this._price = price;
    this._priceLabel =
      price !== null && Number.isFinite(price)
        ? `▶ ${price.toFixed(3)}`
        : '▶ Now';
    this._param?.requestUpdate();

    // Schedule a deferred update so the line renders even if the chart
    // hasn't finished its layout when setPosition is first called.
    this._scheduleDeferredUpdate();
  }

  /** Hide the line */
  clear(): void {
    this._cancelDeferredUpdate();
    this._timestamp = null;
    this._price = null;
    this._priceLabel = '';
    this._param?.requestUpdate();
  }

  private _scheduleDeferredUpdate(): void {
    this._cancelDeferredUpdate();
    // Use double-rAF to ensure the chart has completed its layout
    // (fitContent / setData may schedule their own rAF internally)
    this._deferredUpdateId = requestAnimationFrame(() => {
      this._deferredUpdateId = requestAnimationFrame(() => {
        this._deferredUpdateId = null;
        this._param?.requestUpdate();
      });
    });
  }

  private _cancelDeferredUpdate(): void {
    if (this._deferredUpdateId !== null) {
      cancelAnimationFrame(this._deferredUpdateId);
      this._deferredUpdateId = null;
    }
  }

  updateAllViews(): void {
    // paneViews re-read state on each render
  }

  paneViews(): readonly IPrimitivePaneView[] {
    return this._paneViews;
  }
}
