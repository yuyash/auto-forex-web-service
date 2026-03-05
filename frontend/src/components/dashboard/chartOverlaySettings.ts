export interface OverlaySettings {
  sma20: boolean;
  sma50: boolean;
  ema12: boolean;
  ema26: boolean;
  bollinger: boolean;
  volume: boolean;
  supportResistance: boolean;
  markers: boolean;
}

export const DEFAULT_OVERLAY_SETTINGS: OverlaySettings = {
  sma20: true,
  sma50: false,
  ema12: false,
  ema26: false,
  bollinger: true,
  volume: true,
  supportResistance: false,
  markers: false,
};
