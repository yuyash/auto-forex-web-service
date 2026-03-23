import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';

export function createQueryHookWrapper(options?: { gcTime?: number }) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        ...(options?.gcTime !== undefined ? { gcTime: options.gcTime } : {}),
      },
    },
  });

  return {
    queryClient,
    wrapper: ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    ),
  };
}
