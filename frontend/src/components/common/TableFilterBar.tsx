import { Box, type SxProps, type Theme } from '@mui/material';
import type { ReactNode } from 'react';

interface TableFilterBarProps {
  children: ReactNode;
  sx?: SxProps<Theme>;
}

export function TableFilterBar({ children, sx }: TableFilterBarProps) {
  const extraSx = Array.isArray(sx) ? sx : [sx];

  return (
    <Box
      data-testid="table-filter-bar"
      sx={[
        {
          mb: 2,
          display: 'flex',
          gap: 1,
          flexWrap: 'wrap',
          alignItems: { xs: 'stretch', sm: 'center' },
          p: 0,
        },
        ...extraSx,
      ]}
    >
      {children}
    </Box>
  );
}
