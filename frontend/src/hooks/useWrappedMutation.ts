import { useMutation, type UseMutationOptions } from '@tanstack/react-query';

interface MutationResult<TData, TVariables> {
  data: TData | null;
  isLoading: boolean;
  error: Error | null;
  mutate: (variables: TVariables) => Promise<TData>;
  reset: () => void;
}

export function useWrappedMutation<TData, TVariables>(
  mutationFn: (variables: TVariables) => Promise<TData>,
  options?: UseMutationOptions<TData, Error, TVariables>
): MutationResult<TData, TVariables> {
  const mutation = useMutation<TData, Error, TVariables>({
    mutationFn,
    ...options,
  });

  return {
    data: mutation.data ?? null,
    isLoading: mutation.isPending,
    error: mutation.error ?? null,
    mutate: mutation.mutateAsync,
    reset: mutation.reset,
  };
}
