import { useCallback, useState, type DragEvent } from 'react';
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

export interface ItemOrderDialogItem {
  id: string;
  label: string;
  secondary?: string;
}

interface ItemOrderDialogProps {
  open: boolean;
  title: string;
  description: string;
  items: ItemOrderDialogItem[];
  onClose: () => void;
  onSave: (ids: string[]) => void;
  onReset: () => void;
}

export function ItemOrderDialog({
  open,
  title,
  description,
  items,
  onClose,
  onSave,
  onReset,
}: ItemOrderDialogProps) {
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

  const handleDragStart = useCallback((event: DragEvent, index: number) => {
    setDragIndex(index);
    event.dataTransfer.effectAllowed = 'move';
  }, []);

  const handleDragOver = useCallback(
    (event: DragEvent, index: number) => {
      event.preventDefault();
      event.dataTransfer.dropEffect = 'move';
      if (dragIndex !== null && dragIndex !== index) {
        moveItem(dragIndex, index);
        setDragIndex(index);
      }
    },
    [dragIndex, moveItem]
  );

  const handleDragEnd = useCallback(() => setDragIndex(null), []);

  const handleSave = useCallback(() => {
    onSave(localItems.map((item) => item.id));
    onClose();
  }, [localItems, onClose, onSave]);

  const handleReset = useCallback(() => {
    onReset();
    onClose();
  }, [onClose, onReset]);

  return (
    <Dialog open={open} onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle>{title}</DialogTitle>
      <DialogContent dividers>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          {description}
        </Typography>
        <List dense disablePadding>
          {localItems.map((item, index) => (
            <ListItem
              key={item.id}
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
                    aria-label={t('itemOrder.moveUp')}
                  >
                    <ArrowUpIcon fontSize="small" />
                  </IconButton>
                  <IconButton
                    edge="end"
                    size="small"
                    onClick={() => moveItem(index, index + 1)}
                    disabled={index === localItems.length - 1}
                    aria-label={t('itemOrder.moveDown')}
                  >
                    <ArrowDownIcon fontSize="small" />
                  </IconButton>
                </Box>
              }
            >
              <ListItemIcon sx={{ minWidth: 32 }}>
                <DragIcon fontSize="small" sx={{ color: 'text.secondary' }} />
              </ListItemIcon>
              <ListItemText primary={item.label} secondary={item.secondary} />
            </ListItem>
          ))}
        </List>
      </DialogContent>
      <DialogActions>
        <Button onClick={handleReset} color="inherit" sx={{ mr: 'auto' }}>
          {t('itemOrder.reset')}
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
