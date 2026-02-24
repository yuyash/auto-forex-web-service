/**
 * TableSelectionToolbar Component
 *
 * Reusable toolbar with copy, select-all, reset, and reload buttons
 * for tables with row selection support.
 */

import React from 'react';
import { Box, IconButton, Tooltip, Typography } from '@mui/material';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import SelectAllIcon from '@mui/icons-material/SelectAll';
import DeselectIcon from '@mui/icons-material/Deselect';
import RefreshIcon from '@mui/icons-material/Refresh';

interface TableSelectionToolbarProps {
  selectedCount: number;
  onCopy: () => void;
  onSelectAll: () => void;
  onReset: () => void;
  onReload: () => void;
  isReloading?: boolean;
}

export const TableSelectionToolbar: React.FC<TableSelectionToolbarProps> = ({
  selectedCount,
  onCopy,
  onSelectAll,
  onReset,
  onReload,
  isReloading = false,
}) => {
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
      {selectedCount > 0 && (
        <Typography variant="caption" color="text.secondary">
          ({selectedCount} selected)
        </Typography>
      )}
      <Tooltip title="Copy selected rows">
        <span>
          <IconButton onClick={onCopy} disabled={selectedCount === 0}>
            <ContentCopyIcon fontSize="small" />
          </IconButton>
        </span>
      </Tooltip>
      <Tooltip title="Select all on page">
        <IconButton onClick={onSelectAll}>
          <SelectAllIcon fontSize="small" />
        </IconButton>
      </Tooltip>
      <Tooltip title="Reset selection">
        <span>
          <IconButton onClick={onReset} disabled={selectedCount === 0}>
            <DeselectIcon fontSize="small" />
          </IconButton>
        </span>
      </Tooltip>
      <Tooltip title="Reload data">
        <IconButton onClick={onReload} disabled={isReloading}>
          <RefreshIcon fontSize="small" />
        </IconButton>
      </Tooltip>
    </Box>
  );
};
