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

export interface Position {
  position_id: string;
  instrument: string;
  direction: 'long' | 'short';
  units: number;
  entry_price: number;
  current_price: number;
  unrealized_pnl: number;
  opened_at: string;
  take_profit?: number;
  stop_loss?: number;
}

export interface Order {
  order_id: string;
  instrument: string;
  order_type: 'market' | 'limit' | 'stop' | 'oco';
  direction: 'long' | 'short';
  units: number;
  price?: number;
  take_profit?: number;
  stop_loss?: number;
  status: string;
  created_at: string;
}

export interface StrategyEvent {
  id: string;
  strategy_name: string;
  event_type: 'SIGNAL' | 'ORDER' | 'POSITION' | 'ERROR';
  message: string;
  timestamp: string; // ISO format
  instrument?: string;
  price?: number;
  direction?: 'long' | 'short';
}
