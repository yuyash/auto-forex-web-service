export interface OHLCData {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
}

export interface TickData {
  instrument: string;
  time: string;
  bid: number;
  ask: number;
  mid: number;
  spread: number;
}

export type Granularity =
  | 'S5'
  | 'S10'
  | 'S15'
  | 'S30'
  | 'M1'
  | 'M2'
  | 'M4'
  | 'M5'
  | 'M10'
  | 'M15'
  | 'M30'
  | 'H1'
  | 'H2'
  | 'H3'
  | 'H4'
  | 'H6'
  | 'H8'
  | 'H12'
  | 'D'
  | 'W'
  | 'M';

export interface ChartConfig {
  width?: number;
  height?: number;
  upColor?: string;
  downColor?: string;
  borderVisible?: boolean;
  wickUpColor?: string;
  wickDownColor?: string;
}
