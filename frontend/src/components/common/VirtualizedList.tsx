// Virtualized list component for efficient rendering of large datasets
import React from 'react';
import { FixedSizeList, ListChildComponentProps } from 'react-window';
import { Box, Typography } from '@mui/material';

interface VirtualizedListProps<T> {
  items: T[];
  itemHeight: number;
  height: number;
  width?: string | number;
  renderItem: (item: T, index: number) => React.ReactNode;
  emptyMessage?: string;
  overscanCount?: number;
}

export function VirtualizedList<T>({
  items,
  itemHeight,
  height,
  width = '100%',
  renderItem,
  emptyMessage = 'No items to display',
  overscanCount = 5,
}: VirtualizedListProps<T>) {
  const Row = React.useCallback(
    ({ index, style }: ListChildComponentProps) => {
      const item = items[index];
      return (
        <div style={style} key={index}>
          {renderItem(item, index)}
        </div>
      );
    },
    [items, renderItem]
  );

  if (items.length === 0) {
    return (
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          height,
          width,
        }}
      >
        <Typography variant="body2" color="text.secondary">
          {emptyMessage}
        </Typography>
      </Box>
    );
  }

  return (
    <FixedSizeList
      height={height}
      itemCount={items.length}
      itemSize={itemHeight}
      width={width}
      overscanCount={overscanCount}
    >
      {Row}
    </FixedSizeList>
  );
}

export default VirtualizedList;
