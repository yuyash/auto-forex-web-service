import '@testing-library/jest-dom/vitest';
import '../i18n/config';

// Node.js 22+ exposes a built-in localStorage that lacks standard Storage
// methods (clear, key, length, etc.), which shadows jsdom's implementation.
// Replace it with a spec-compliant in-memory Storage polyfill.
if (
  typeof localStorage !== 'undefined' &&
  typeof localStorage.clear !== 'function'
) {
  const store = new Map<string, string>();
  const storage: Storage = {
    get length() {
      return store.size;
    },
    clear() {
      store.clear();
    },
    getItem(key: string) {
      return store.get(key) ?? null;
    },
    key(index: number) {
      return [...store.keys()][index] ?? null;
    },
    removeItem(key: string) {
      store.delete(key);
    },
    setItem(key: string, value: string) {
      store.set(key, String(value));
    },
  };
  Object.defineProperty(globalThis, 'localStorage', {
    value: storage,
    writable: true,
    configurable: true,
  });
}

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

const createJsonResponse = (data: unknown, init?: ResponseInit): Response => {
  return new Response(JSON.stringify(data), {
    status: 200,
    headers: {
      'Content-Type': 'application/json',
    },
    ...init,
  });
};

// Provide a default response for AuthProvider's public settings fetch.
// In Node test environments, the native fetch implementation may not accept
// relative URLs (e.g. '/api/...'), which leads to noisy console errors.
const originalFetch = globalThis.fetch;
if (typeof originalFetch === 'function') {
  globalThis.fetch = (async (
    input: RequestInfo | URL,
    init?: RequestInit
  ): Promise<Response> => {
    if (
      typeof input === 'string' &&
      input === '/api/accounts/settings/public'
    ) {
      return createJsonResponse({
        registration_enabled: true,
        login_enabled: true,
      });
    }

    return originalFetch(input as RequestInfo, init);
  }) as typeof fetch;
}
