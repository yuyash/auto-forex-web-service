/**
 * EventDetailDialog Component
 *
 * Displays a task event's full JSON data in a formatted, readable dialog.
 */

import React, { useCallback } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Chip,
  IconButton,
  Tooltip,
  Typography,
} from '@mui/material';
import {
  ContentCopy as CopyIcon,
  Close as CloseIcon,
} from '@mui/icons-material';
import { useTranslation } from 'react-i18next';
import type { TaskEvent } from '../../../hooks/useTaskEvents';

interface EventDetailDialogProps {
  open: boolean;
  event: TaskEvent | null;
  onClose: () => void;
}

export const EventDetailDialog: React.FC<EventDetailDialogProps> = ({
  open,
  event,
  onClose,
}) => {
  const { t } = useTranslation('common');

  const getSeverityColor = (
    severity: string
  ): 'default' | 'error' | 'warning' | 'info' => {
    switch (severity?.toLowerCase()) {
      case 'error':
      case 'critical':
        return 'error';
      case 'warning':
        return 'warning';
      case 'info':
        return 'info';
      default:
        return 'default';
    }
  };

  const jsonString = React.useMemo(() => {
    if (!event) return '';
    return JSON.stringify(event, null, 2);
  }, [event]);

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(jsonString);
  }, [jsonString]);

  if (!event) return null;

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="md"
      fullWidth
      aria-labelledby="event-detail-dialog-title"
    >
      <DialogTitle id="event-detail-dialog-title">
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, pr: 4 }}>
          <Typography variant="h6" component="span" sx={{ flexShrink: 0 }}>
            {t('tables.events.detailTitle')}
          </Typography>
          <Chip
            label={event.event_type_display ?? event.event_type}
            size="small"
            variant="outlined"
          />
          <Chip
            label={event.severity}
            size="small"
            color={getSeverityColor(event.severity)}
          />
          <Box sx={{ flex: 1 }} />
          <IconButton
            aria-label={t('actions.close')}
            onClick={onClose}
            sx={{ position: 'absolute', right: 8, top: 8 }}
          >
            <CloseIcon />
          </IconButton>
        </Box>
      </DialogTitle>
      <DialogContent dividers>
        <Box
          component="pre"
          sx={{
            m: 0,
            p: 2,
            borderRadius: 1,
            bgcolor: 'grey.900',
            color: 'grey.100',
            fontSize: '0.8125rem',
            lineHeight: 1.6,
            overflow: 'auto',
            maxHeight: '60vh',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
            fontFamily: '"Fira Code", "Cascadia Code", "Consolas", monospace',
          }}
        >
          {jsonString}
        </Box>
      </DialogContent>
      <DialogActions>
        <Tooltip title={t('tables.events.copyJson')}>
          <Button onClick={handleCopy} startIcon={<CopyIcon />}>
            {t('tables.events.copyJson')}
          </Button>
        </Tooltip>
        <Button onClick={onClose} variant="contained">
          {t('actions.close')}
        </Button>
      </DialogActions>
    </Dialog>
  );
};
