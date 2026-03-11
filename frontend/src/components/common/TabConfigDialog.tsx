/**
 * TabConfigDialog Component
 *
 * Dialog for configuring tab visibility and order.
 * Users can toggle tabs on/off and reorder them via drag-and-drop.
 * The "overview" tab is always visible and pinned at the top.
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
import type { TabItem } from '../../hooks/useTabConfig';

interface TabConfigDialogProps {
  open: boolean;
  tabs: TabItem[];
  onClose: () => void;
  onSave: (tabs: TabItem[]) => void;
  onReset: () => void;
}

export const TabConfigDialog: React.FC<TabConfigDialogProps> = ({
  open,
  tabs,
  onClose,
  onSave,
  onReset,
}) => {
  const { t } = useTranslation('common');
  const [localTabs, setLocalTabs] = useState<TabItem[]>(tabs);
  const [dragIndex, setDragIndex] = useState<number | null>(null);

  // Reset local state when dialog opens
  React.useEffect(() => {
    if (open) {
      setLocalTabs(tabs);
    }
  }, [open, tabs]);

  const handleToggle = useCallback((id: string) => {
    setLocalTabs((prev) =>
      prev.map((tab) =>
        tab.id === id ? { ...tab, visible: !tab.visible } : tab
      )
    );
  }, []);

  const moveTab = useCallback((fromIndex: number, toIndex: number) => {
    setLocalTabs((prev) => {
      const updated = [...prev];
      const [moved] = updated.splice(fromIndex, 1);
      updated.splice(toIndex, 0, moved);
      return updated;
    });
  }, []);

  const handleDragStart = useCallback(
    (e: React.DragEvent, index: number) => {
      // Don't allow dragging the overview tab
      if (localTabs[index].id === 'overview') return;
      setDragIndex(index);
      e.dataTransfer.effectAllowed = 'move';
    },
    [localTabs]
  );

  const handleDragOver = useCallback(
    (e: React.DragEvent, index: number) => {
      e.preventDefault();
      // Don't allow dropping onto the overview tab position
      if (localTabs[index].id === 'overview') return;
      if (dragIndex !== null && dragIndex !== index) {
        moveTab(dragIndex, index);
        setDragIndex(index);
      }
    },
    [dragIndex, moveTab, localTabs]
  );

  const handleDragEnd = useCallback(() => {
    setDragIndex(null);
  }, []);

  const handleMoveUp = useCallback(
    (index: number) => {
      // Find previous non-overview position
      const targetIndex = index - 1;
      if (targetIndex >= 0 && localTabs[targetIndex].id !== 'overview') {
        moveTab(index, targetIndex);
      }
    },
    [moveTab, localTabs]
  );

  const handleMoveDown = useCallback(
    (index: number) => {
      if (index < localTabs.length - 1) {
        moveTab(index, index + 1);
      }
    },
    [moveTab, localTabs]
  );

  const handleSave = useCallback(() => {
    onSave(localTabs);
    onClose();
  }, [localTabs, onSave, onClose]);

  const handleReset = useCallback(() => {
    onReset();
    onClose();
  }, [onReset, onClose]);

  const visibleCount = localTabs.filter((t) => t.visible).length;

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="xs"
      fullWidth
      fullScreen={false}
      aria-labelledby="tab-config-dialog-title"
      sx={{
        '& .MuiDialog-paper': {
          margin: { xs: 1, sm: 4 },
          width: { xs: 'calc(100% - 16px)', sm: undefined },
          maxHeight: { xs: 'calc(100% - 16px)', sm: undefined },
        },
      }}
    >
      <DialogTitle id="tab-config-dialog-title">
        {t('tabConfig.title')}
      </DialogTitle>
      <DialogContent dividers>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          {t('tabConfig.description')}
        </Typography>
        <List dense disablePadding>
          {localTabs.map((tab, index) => {
            const isOverview = tab.id === 'overview';
            const isFirst =
              index === 0 || localTabs[index - 1]?.id === 'overview';
            const isLast = index === localTabs.length - 1;

            return (
              <ListItem
                key={tab.id}
                draggable={!isOverview}
                onDragStart={(e) => handleDragStart(e, index)}
                onDragOver={(e) => handleDragOver(e, index)}
                onDragEnd={handleDragEnd}
                sx={{
                  cursor: isOverview ? 'default' : 'grab',
                  bgcolor: dragIndex === index ? 'action.hover' : 'transparent',
                  borderRadius: 1,
                  mb: 0.5,
                  opacity: isOverview ? 0.7 : 1,
                  '&:hover': {
                    bgcolor: 'action.hover',
                  },
                }}
                secondaryAction={
                  !isOverview && (
                    <Box sx={{ display: 'flex', gap: 0 }}>
                      <IconButton
                        edge="end"
                        size="small"
                        onClick={() => handleMoveUp(index)}
                        disabled={isFirst}
                        aria-label={t('tabConfig.moveUp')}
                      >
                        <ArrowUpIcon fontSize="small" />
                      </IconButton>
                      <IconButton
                        edge="end"
                        size="small"
                        onClick={() => handleMoveDown(index)}
                        disabled={isLast}
                        aria-label={t('tabConfig.moveDown')}
                      >
                        <ArrowDownIcon fontSize="small" />
                      </IconButton>
                    </Box>
                  )
                }
              >
                <ListItemIcon sx={{ minWidth: 32 }}>
                  {isOverview ? (
                    <Box sx={{ width: 24 }} />
                  ) : (
                    <DragIcon
                      fontSize="small"
                      sx={{ color: 'text.secondary' }}
                    />
                  )}
                </ListItemIcon>
                <ListItemIcon sx={{ minWidth: 40 }}>
                  <Checkbox
                    edge="start"
                    checked={tab.visible}
                    onChange={() => handleToggle(tab.id)}
                    disabled={isOverview || (tab.visible && visibleCount <= 2)}
                    inputProps={{
                      'aria-label': tab.label,
                    }}
                    size="small"
                  />
                </ListItemIcon>
                <ListItemText primary={tab.label} />
              </ListItem>
            );
          })}
        </List>
      </DialogContent>
      <DialogActions sx={{ flexWrap: 'wrap', gap: 1 }}>
        <Button
          onClick={handleReset}
          color="inherit"
          sx={{ mr: { xs: 0, sm: 'auto' } }}
        >
          {t('tabConfig.reset')}
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
