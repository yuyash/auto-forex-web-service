import { api } from '../../api/apiClient';
import type { BacktestInitialPositionCycle } from '../../types/backtestTask';

export type InitialPositionTaskType = 'backtest' | 'trading';

export interface InitialPositionImportSource {
  task_type: InitialPositionTaskType;
  id: string;
  name: string;
  status: string;
  instrument: string;
  config_id: string;
  config_name: string;
  strategy_type: string;
  updated_at?: string | null;
}

export interface InitialPositionImportSourceList {
  results: InitialPositionImportSource[];
}

export interface InitialPositionImportResult {
  cycles: BacktestInitialPositionCycle[];
  source: 'task' | 'oanda';
  summary: {
    cycles: number;
    positions: number;
    open: number;
    pending: number;
    closed_slots: number;
    skipped_positions?: number;
    skipped_layer_limit?: number;
    skipped_retracement_limit?: number;
    target_max_layer?: number | null;
    target_max_retracement?: number | null;
  };
}

export interface ImportFromTaskRequest {
  source_task_type: InitialPositionTaskType;
  source_task_id: string;
  target_task_type: InitialPositionTaskType;
  target_config_id?: string;
}

export interface ImportFromOandaRequest {
  account_id: number | string;
  config_id: string;
  instrument: string;
}

export const initialPositionImportsApi = {
  listSources: (): Promise<InitialPositionImportSourceList> =>
    api.get<InitialPositionImportSourceList>(
      '/api/trading/tasks/initial-position-import-sources/'
    ),

  importFromTask: (
    data: ImportFromTaskRequest
  ): Promise<InitialPositionImportResult> =>
    api.post<InitialPositionImportResult>(
      '/api/trading/tasks/initial-positions/import-from-task/',
      data
    ),

  importFromOanda: (
    data: ImportFromOandaRequest
  ): Promise<InitialPositionImportResult> =>
    api.post<InitialPositionImportResult>(
      '/api/trading/tasks/initial-positions/import-from-oanda/',
      data
    ),
};
