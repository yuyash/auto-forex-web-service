import type {
  ConfigurationTask,
  PaginatedResponse,
  StrategyConfig,
  StrategyConfigListParams,
} from '../types';
import {
  createConfigurationQuery,
  createConfigurationsQuery,
  createConfigurationTasksQuery,
} from './configurationQueries';
import {
  type QueryStateResult,
  useTaskDetail,
  useTaskList,
} from './useTaskCollections';

type UseConfigurationsResult = QueryStateResult<
  PaginatedResponse<StrategyConfig>
>;
type UseConfigurationResult = QueryStateResult<StrategyConfig>;
type UseConfigurationTasksResult = QueryStateResult<ConfigurationTask[]>;

export function useConfigurations(
  params?: StrategyConfigListParams
): UseConfigurationsResult {
  return useTaskList(createConfigurationsQuery(params));
}

export function useConfiguration(id?: string): UseConfigurationResult {
  return useTaskDetail(
    createConfigurationQuery(id),
    id ? undefined : async () => undefined
  );
}

export function useConfigurationTasks(
  id: string,
  options?: { enabled?: boolean }
): UseConfigurationTasksResult {
  return useTaskList(createConfigurationTasksQuery(id, options));
}
