import '@testing-library/jest-dom/vitest';
import '../i18n/config';

// Mock window.matchMedia
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {}, // deprecated
    removeListener: () => {}, // deprecated
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => true,
  }),
});

// Mock HTMLCanvasElement.getContext for react-financial-charts
const originalGetContext = HTMLCanvasElement.prototype.getContext;
HTMLCanvasElement.prototype.getContext = function (
  this: HTMLCanvasElement,
  contextId: string,
  options?: CanvasRenderingContext2DSettings
) {
  if (contextId === '2d') {
    return {
      fillStyle: '',
      strokeStyle: '',
      lineWidth: 1,
      lineCap: 'butt',
      lineJoin: 'miter',
      miterLimit: 10,
      lineDashOffset: 0,
      shadowOffsetX: 0,
      shadowOffsetY: 0,
      shadowBlur: 0,
      shadowColor: 'transparent',
      globalAlpha: 1,
      globalCompositeOperation: 'source-over',
      font: '10px sans-serif',
      textAlign: 'start',
      textBaseline: 'alphabetic',
      direction: 'ltr',
      imageSmoothingEnabled: true,
      fillRect: () => {},
      clearRect: () => {},
      strokeRect: () => {},
      beginPath: () => {},
      closePath: () => {},
      moveTo: () => {},
      lineTo: () => {},
      bezierCurveTo: () => {},
      quadraticCurveTo: () => {},
      arc: () => {},
      arcTo: () => {},
      ellipse: () => {},
      rect: () => {},
      fill: () => {},
      stroke: () => {},
      clip: () => {},
      isPointInPath: () => false,
      isPointInStroke: () => false,
      rotate: () => {},
      scale: () => {},
      translate: () => {},
      transform: () => {},
      setTransform: () => {},
      resetTransform: () => {},
      drawImage: () => {},
      createImageData: () => ({
        data: new Uint8ClampedArray(),
        width: 0,
        height: 0,
      }),
      getImageData: () => ({
        data: new Uint8ClampedArray(),
        width: 0,
        height: 0,
      }),
      putImageData: () => {},
      save: () => {},
      restore: () => {},
      createLinearGradient: () => ({
        addColorStop: () => {},
      }),
      createRadialGradient: () => ({
        addColorStop: () => {},
      }),
      createPattern: () => null,
      setLineDash: () => {},
      getLineDash: () => [],
      measureText: (text: string) => ({
        width: text.length * 8,
        actualBoundingBoxLeft: 0,
        actualBoundingBoxRight: text.length * 8,
        actualBoundingBoxAscent: 10,
        actualBoundingBoxDescent: 2,
        fontBoundingBoxAscent: 10,
        fontBoundingBoxDescent: 2,
        alphabeticBaseline: 0,
        hangingBaseline: 0,
        ideographicBaseline: 0,
        emHeightAscent: 0,
        emHeightDescent: 0,
      }),
      fillText: () => {},
      strokeText: () => {},
      drawFocusIfNeeded: () => {},
      scrollPathIntoView: () => {},
      canvas: this,
    } as unknown as CanvasRenderingContext2D;
  }
  return originalGetContext?.call(this, contextId, options) || null;
};
