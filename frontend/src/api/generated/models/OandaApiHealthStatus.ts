/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type OandaApiHealthStatus = {
  readonly id: number;
  readonly account: number;
  readonly oanda_account_id: string;
  readonly api_type: string;
  readonly is_available: boolean;
  readonly checked_at: string;
  readonly latency_ms: number | null;
  readonly http_status: number | null;
  readonly error_message: string;
};
