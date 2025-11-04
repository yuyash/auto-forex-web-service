export interface Order extends Record<string, unknown> {
  id: string;
  order_id: string;
  instrument: string;
  order_type: 'MARKET' | 'LIMIT' | 'STOP' | 'OCO';
  direction: 'BUY' | 'SELL';
  units: number;
  price: number | null;
  status: 'PENDING' | 'FILLED' | 'CANCELLED' | 'REJECTED';
  created_at: string;
  filled_at: string | null;
  account: number;
  user: number;
}

export interface OrderFilters {
  start_date?: string;
  end_date?: string;
  instrument?: string;
  status?: string;
  order_id?: string;
}

export interface OrdersResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: Order[];
}
