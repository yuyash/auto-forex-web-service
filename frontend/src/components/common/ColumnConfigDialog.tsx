/**
 * ColumnConfigDialog Component
 *
 * Dialog for configuring table column visibility and order.
 * Users can toggle columns on/off and reorder them via drag or arrow buttons.
 */

import React, { useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Checkbox,
  IconButton,
  Typography,
  Box,
} from '@mui/material';
import {
  DragIndicator as DragIcon,
  ArrowUpward as ArrowUpIcon,
  ArrowDownward as ArrowDownIcon,
} from '@mui/icons-material';
import type { ColumnItem } from '../../hooks/useColumnConfig';

interface ColumnConfigDialogProps {
  open: boolean;
  columns: ColumnItem[];
  onClose: () => void;
  onSave: (columns: ColumnItem[]) => void;
  onReset: () => void;
  title?: string;
}

export const ColumnConfigDialog: React.FC<ColumnConfigDialogProps> = ({
  open,
  columns,
  onClose,
  onSave,
  onReset,
  title,
}) => {
  const { t } = useTranslation('common');
  const [local, setLocal] = useState<ColumnItem[]>(columns);
  const [dragIndex, setDragIndex] = useState<number | null>(null);

  React.useEffect(() => {
    if (open) setLocal(columns);
  }, [open, columns]);

  const handleToggle = useCallback((id: string) => {
    setLocal((prev) =>
      prev.map((col) =>
        col.id === id ? { ...col, visible: !col.visible } : col
      )
    );
  }, []);

  const moveCol = useCallback((from: number, to: number) => {
    setLocal((prev) => {
      const updated = [...prev];
      const [moved] = updated.splice(from, 1);
      updated.splice(to, 0, moved);
      return updated;
    });
  }, []);

  const handleDragStart = useCallback((e: React.DragEvent, index: number) => {
    setDragIndex(index);
    e.dataTransfer.effectAllowed = 'move';
  }, []);

  const handleDragOver = useCallback(
    (e: React.DragEvent, index: number) => {
      e.preventDefault();
      if (dragIndex !== null && dragIndex !== index) {
        moveCol(dragIndex, index);
        setDragIndex(index);
      }
    },
    [dragIndex, moveCol]
  );

  const handleDragEnd = useCallback(() => setDragIndex(null), []);

  const handleSave = useCallback(() => {
    onSave(local);
    onClose();
  }, [local, onSave, onClose]);

  const handleReset = useCallback(() => {
    onReset();
    onClose();
  }, [onReset, onClose]);

  const visibleCount = local.filter((c) => c.visible).length;

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="xs"
      fullWidth
      aria-labelledby="column-config-dialog-title"
    >
      <DialogTitle id="column-config-dialog-title">
        {title || t('columnConfig.title')}
      </DialogTitle>
      <DialogContent dividers>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          {t('columnConfig.description')}
        </Typography>
        <List dense disablePadding>
          {local.map((col, index) => (
            <ListItem
              key={col.id}
              draggable
              onDragStart={(e) => handleDragStart(e, index)}
              onDragOver={(e) => handleDragOver(e, index)}
              onDragEnd={handleDragEnd}
              sx={{
                cursor: 'grab',
                bgcolor: dragIndex === index ? 'action.hover' : 'transparent',
                borderRadius: 1,
                mb: 0.5,
                '&:hover': { bgcolor: 'action.hover' },
              }}
              secondaryAction={
                <Box sx={{ display: 'flex', gap: 0 }}>
                  <IconButton
                    edge="end"
                    size="small"
                    onClick={() => index > 0 && moveCol(index, index - 1)}
                    disabled={index === 0}
                    aria-label={t('columnConfig.moveUp')}
                  >
                    <ArrowUpIcon fontSize="small" />
                  </IconButton>
                  <IconButton
                    edge="end"
                    size="small"
                    onClick={() =>
                      index < local.length - 1 && moveCol(index, index + 1)
                    }
                    disabled={index === local.length - 1}
                    aria-label={t('columnConfig.moveDown')}
                  >
                    <ArrowDownIcon fontSize="small" />
                  </IconButton>
                </Box>
              }
            >
              <ListItemIcon sx={{ minWidth: 32 }}>
                <DragIcon fontSize="small" sx={{ color: 'text.secondary' }} />
              </ListItemIcon>
              <ListItemIcon sx={{ minWidth: 40 }}>
                <Checkbox
                  edge="start"
                  checked={col.visible}
                  onChange={() => handleToggle(col.id)}
                  disabled={col.visible && visibleCount <= 1}
                  inputProps={{ 'aria-label': col.label }}
                  size="small"
                />
              </ListItemIcon>
              <ListItemText primary={col.label} />
            </ListItem>
          ))}
        </List>
      </DialogContent>
      <DialogActions>
        <Button onClick={handleReset} color="inherit" sx={{ mr: 'auto' }}>
          {t('columnConfig.reset')}
        </Button>
        <Button onClick={onClose} color="inherit">
          {t('actions.cancel')}
        </Button>
        <Button onClick={handleSave} variant="contained">
          {t('actions.save')}
        </Button>
      </DialogActions>
    </Dialog>
  );
};
