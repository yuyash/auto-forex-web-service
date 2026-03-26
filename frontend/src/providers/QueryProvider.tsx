// React Query provider with devtools
import { useState, useEffect } from 'react';
import { QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { queryClient, onQueryClientChange } from '../config/reactQuery';
import type { QueryClient } from '@tanstack/react-query';

interface QueryProviderProps {
  children: React.ReactNode;
}

export function QueryProvider({ children }: QueryProviderProps) {
  const [client, setClient] = useState<QueryClient>(() => queryClient);

  useEffect(() => {
    // When the authenticated user changes, reactQuery.ts replaces the
    // module-level queryClient and notifies us here so we re-render with
    // the new instance.  This guarantees that every useQueryClient() call
    // in the tree returns the user-scoped client.
    return onQueryClientChange((newClient) => setClient(newClient));
  }, []);

  return (
    <QueryClientProvider client={client}>
      {children}
      {/* Only show devtools in development */}
      {import.meta.env.DEV && (
        <ReactQueryDevtools
          initialIsOpen={false}
          position="bottom"
          buttonPosition="bottom-right"
        />
      )}
    </QueryClientProvider>
  );
}

export default QueryProvider;
