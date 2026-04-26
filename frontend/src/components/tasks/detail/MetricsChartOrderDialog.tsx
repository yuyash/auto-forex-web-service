import { useCallback, useState, type DragEvent as ReactDragEvent } from 'react';
import {
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Typography,
} from '@mui/material';
import {
  ArrowDownward as ArrowDownIcon,
  ArrowUpward as ArrowUpIcon,
  DragIndicator as DragIcon,
} from '@mui/icons-material';
import { useTranslation } from 'react-i18next';

export interface MetricsChartOrderItem {
  key: string;
  label: string;
  color?: string;
}

interface MetricsChartOrderDialogProps {
  open: boolean;
  items: MetricsChartOrderItem[];
  onClose: () => void;
  onSave: (keys: string[]) => void;
  onReset: () => void;
}

export function MetricsChartOrderDialog({
  open,
  items,
  onClose,
  onSave,
  onReset,
}: MetricsChartOrderDialogProps) {
  const { t } = useTranslation('common');
  const [localItems, setLocalItems] = useState(items);
  const [dragIndex, setDragIndex] = useState<number | null>(null);

  const moveItem = useCallback((from: number, to: number) => {
    setLocalItems((current) => {
      if (from < 0 || to < 0 || from === to || to >= current.length) {
        return current;
      }
      const next = [...current];
      const [moved] = next.splice(from, 1);
      next.splice(to, 0, moved);
      return next;
    });
  }, []);

  const handleDragStart = useCallback((e: ReactDragEvent, index: number) => {
    setDragIndex(index);
    e.dataTransfer.effectAllowed = 'move';
  }, []);

  const handleDragOver = useCallback(
    (e: ReactDragEvent, index: number) => {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';
      if (dragIndex !== null && dragIndex !== index) {
        moveItem(dragIndex, index);
        setDragIndex(index);
      }
    },
    [dragIndex, moveItem]
  );

  const handleDragEnd = useCallback(() => setDragIndex(null), []);

  const handleSave = useCallback(() => {
    onSave(localItems.map((item) => item.key));
    onClose();
  }, [localItems, onClose, onSave]);

  const handleReset = useCallback(() => {
    onReset();
    onClose();
  }, [onClose, onReset]);

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="xs"
      fullWidth
      aria-labelledby="metrics-chart-order-dialog-title"
    >
      <DialogTitle id="metrics-chart-order-dialog-title">
        {t('metrics.chartOrderTitle', 'Chart order')}
      </DialogTitle>
      <DialogContent dividers>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          {t(
            'metrics.chartOrderDescription',
            'Drag charts or use the arrow buttons to change their display order.'
          )}
        </Typography>
        <List dense disablePadding>
          {localItems.map((item, index) => (
            <ListItem
              key={item.key}
              draggable
              onDragStart={(event) => handleDragStart(event, index)}
              onDragOver={(event) => handleDragOver(event, index)}
              onDragEnd={handleDragEnd}
              sx={{
                cursor: 'grab',
                bgcolor: dragIndex === index ? 'action.hover' : 'transparent',
                borderRadius: 1,
                mb: 0.5,
                '&:hover': { bgcolor: 'action.hover' },
              }}
              secondaryAction={
                <Box sx={{ display: 'flex' }}>
                  <IconButton
                    edge="end"
                    size="small"
                    onClick={() => moveItem(index, index - 1)}
                    disabled={index === 0}
                    aria-label={t('metrics.moveChartUp', 'Move chart up')}
                  >
                    <ArrowUpIcon fontSize="small" />
                  </IconButton>
                  <IconButton
                    edge="end"
                    size="small"
                    onClick={() => moveItem(index, index + 1)}
                    disabled={index === localItems.length - 1}
                    aria-label={t('metrics.moveChartDown', 'Move chart down')}
                  >
                    <ArrowDownIcon fontSize="small" />
                  </IconButton>
                </Box>
              }
            >
              <ListItemIcon sx={{ minWidth: 32 }}>
                <DragIcon fontSize="small" sx={{ color: 'text.secondary' }} />
              </ListItemIcon>
              <ListItemIcon sx={{ minWidth: 28 }}>
                <Box
                  sx={{
                    width: 10,
                    height: 10,
                    borderRadius: '50%',
                    bgcolor: item.color ?? 'text.disabled',
                    border: '1px solid',
                    borderColor: 'divider',
                  }}
                />
              </ListItemIcon>
              <ListItemText primary={item.label} />
            </ListItem>
          ))}
        </List>
      </DialogContent>
      <DialogActions>
        <Button onClick={handleReset} color="inherit" sx={{ mr: 'auto' }}>
          {t('metrics.resetChartOrder', 'Reset order')}
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
}
