import { api } from '../../api/apiClient';
import { withRetry } from '../../api/client';

export interface HealthResponse {
  status: string;
  timestamp: string;
  version: string;
  components: Record<string, unknown>;
}

export interface OandaAccountSummary {
  id: number;
  account_id: string;
  api_type: string;
}

export interface OandaHealthStatusResponse {
  account: OandaAccountSummary;
  status: Record<string, unknown> | null;
}

export const healthApi = {
  backend: () => withRetry(() => api.get<HealthResponse>('/api/health/')),
  getOandaStatus: () =>
    api.get<OandaHealthStatusResponse>('/api/market/health/oanda/'),
  checkOandaStatus: () =>
    api.post<OandaHealthStatusResponse>('/api/market/health/oanda/', {}),
};
