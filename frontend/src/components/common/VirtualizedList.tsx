// Virtualized list component - temporarily disabled due to build issues
import React from 'react';
import { Box } from '@mui/material';

interface VirtualizedListProps<T> {
  items: T[];
  itemHeight: number;
  height: number;
  width?: string | number;
  renderItem: (item: T, index: number) => React.ReactNode;
}

export function VirtualizedList<T>({
  items,
  renderItem,
}: VirtualizedListProps<T>) {
  return (
    <Box>
      {items.map((item, index) => (
        <Box key={index}>{renderItem(item, index)}</Box>
      ))}
    </Box>
  );
}
