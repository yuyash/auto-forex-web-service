import type { ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { I18nextProvider } from 'react-i18next';
import { AuthProvider } from '../../src/contexts/AuthContext';
import i18n from '../../src/i18n/config';
import { createQueryHookWrapper } from './queryHookTestUtils';

export function createAuthPageWrapper(initialEntry: string) {
  const { queryClient, wrapper: QueryWrapper } = createQueryHookWrapper();

  return {
    queryClient,
    wrapper: ({ children }: { children: ReactNode }) => (
      <QueryWrapper>
        <I18nextProvider i18n={i18n}>
          <MemoryRouter initialEntries={[initialEntry]}>
            <AuthProvider>{children}</AuthProvider>
          </MemoryRouter>
        </I18nextProvider>
      </QueryWrapper>
    ),
  };
}
