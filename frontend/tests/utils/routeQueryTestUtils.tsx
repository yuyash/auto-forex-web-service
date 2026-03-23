import type { ReactNode } from 'react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { createQueryHookWrapper } from './queryHookTestUtils';

export function createRouteQueryWrapper(options: {
  initialEntry: string;
  path: string;
}) {
  const { queryClient, wrapper: QueryWrapper } = createQueryHookWrapper();

  return {
    queryClient,
    wrapper: ({ children }: { children: ReactNode }) => (
      <QueryWrapper>
        <MemoryRouter initialEntries={[options.initialEntry]}>
          <Routes>
            <Route path={options.path} element={children} />
          </Routes>
        </MemoryRouter>
      </QueryWrapper>
    ),
  };
}
