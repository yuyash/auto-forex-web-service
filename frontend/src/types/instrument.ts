export interface InstrumentMetadata {
  normalized_name: string;
  base_currency: string;
  quote_currency: string;
  pip_size: string;
  is_high_value_quote: boolean;
}

export interface InstrumentsResponse {
  instruments?: string[];
  count?: number;
  source?: string;
  metadata?: Record<string, InstrumentMetadata>;
}

export interface InstrumentDetail extends InstrumentMetadata {
  instrument: string;
  display_name?: string;
  type?: string;
  pip_location?: number;
  pip_value?: number;
  display_precision?: number;
  trade_units_precision?: number;
  minimum_trade_size?: string;
  maximum_trade_units?: string;
  maximum_position_size?: string;
  maximum_order_units?: string;
  margin_rate?: string;
  leverage?: string;
  source?: string;
}
