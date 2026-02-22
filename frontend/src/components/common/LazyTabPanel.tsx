import React from 'react';
import { Box } from '@mui/material';

interface LazyTabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

/**
 * LazyTabPanel — only mounts children when the tab is active.
 * When the user switches away, children are unmounted, stopping
 * any polling intervals, chart instances, etc.
 */
export function LazyTabPanel({
  children,
  value,
  index,
  ...other
}: LazyTabPanelProps) {
  const isActive = value === index;

  return (
    <div
      role="tabpanel"
      hidden={!isActive}
      id={`task-tabpanel-${index}`}
      aria-labelledby={`task-tab-${index}`}
      style={{
        display: isActive ? 'flex' : 'none',
        flexDirection: 'column',
        flex: 1,
        minHeight: 0,
        overflow: 'auto',
      }}
      {...other}
    >
      {isActive && (
        <Box
          sx={{
            pt: 1,
            display: 'flex',
            flexDirection: 'column',
            flex: 1,
            minHeight: 0,
          }}
        >
          {children}
        </Box>
      )}
    </div>
  );
}
