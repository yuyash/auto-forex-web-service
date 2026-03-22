import { Box } from '@mui/material';
import React from 'react';
import { ColumnConfigDialog } from '../../../common/ColumnConfigDialog';
import { TaskTrendPositionsTable } from './TaskTrendPositionsTable';
import { TaskTrendTradesTable } from './TaskTrendTradesTable';

interface TaskTrendTablesSectionProps {
  tradesTableProps: React.ComponentProps<typeof TaskTrendTradesTable>;
  longPositionsTableProps: React.ComponentProps<typeof TaskTrendPositionsTable>;
  shortPositionsTableProps: React.ComponentProps<
    typeof TaskTrendPositionsTable
  >;
  tradeDialogProps: React.ComponentProps<typeof ColumnConfigDialog>;
  longDialogProps: React.ComponentProps<typeof ColumnConfigDialog>;
  shortDialogProps: React.ComponentProps<typeof ColumnConfigDialog>;
}

export function TaskTrendTablesSection({
  tradesTableProps,
  longPositionsTableProps,
  shortPositionsTableProps,
  tradeDialogProps,
  longDialogProps,
  shortDialogProps,
}: TaskTrendTablesSectionProps) {
  return (
    <>
      <Box
        sx={{
          display: 'flex',
          flexDirection: { xs: 'column', lg: 'row' },
          gap: 2,
          mt: 0.5,
          alignItems: 'flex-start',
        }}
      >
        <Box
          sx={{
            flex: 1,
            minWidth: 0,
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          <TaskTrendTradesTable {...tradesTableProps} />
        </Box>

        <TaskTrendPositionsTable {...longPositionsTableProps} />
        <TaskTrendPositionsTable {...shortPositionsTableProps} />
      </Box>

      <ColumnConfigDialog {...tradeDialogProps} />
      <ColumnConfigDialog {...longDialogProps} />
      <ColumnConfigDialog {...shortDialogProps} />
    </>
  );
}
