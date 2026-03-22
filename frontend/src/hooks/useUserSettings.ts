import { queryClient, queryKeys } from '../config/reactQuery';
import { authApi, type UserSettingsResponse } from '../services/api/auth';
import { createUserSettingsQuery } from './miscQueries';
import { useSimpleQueryState } from './useTaskCollections';
import { useWrappedMutation } from './useWrappedMutation';

export function useUserSettings(options?: { enabled?: boolean }) {
  return useSimpleQueryState(createUserSettingsQuery(options));
}

export function useUpdateUserSettings(options?: {
  onSuccess?: (data: UserSettingsResponse) => void;
  onError?: (error: Error) => void;
}) {
  return useWrappedMutation(
    (variables: Record<string, unknown>) =>
      authApi.updateUserSettings(variables),
    {
      onSuccess: async (data) => {
        await queryClient.invalidateQueries({
          queryKey: queryKeys.userSettings.all,
        });
        options?.onSuccess?.(data);
      },
      onError: (error) => options?.onError?.(error),
    }
  );
}
