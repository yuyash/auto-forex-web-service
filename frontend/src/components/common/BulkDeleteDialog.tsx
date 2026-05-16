import { useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Checkbox,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  List,
  ListItem,
  ListItemText,
  Typography,
} from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import WarningIcon from '@mui/icons-material/Warning';
import { useTranslation } from 'react-i18next';

interface BulkDeleteDialogProps {
  open: boolean;
  title: string;
  itemNames: string[];
  onCancel: () => void;
  onConfirm: () => void;
  isLoading?: boolean;
  warning?: string;
}

export function BulkDeleteDialog({
  open,
  title,
  itemNames,
  onCancel,
  onConfirm,
  isLoading = false,
  warning,
}: BulkDeleteDialogProps) {
  const { t } = useTranslation('common');
  const [confirmed, setConfirmed] = useState(false);

  const handleCancel = () => {
    setConfirmed(false);
    onCancel();
  };

  const handleConfirm = () => {
    setConfirmed(false);
    onConfirm();
  };

  return (
    <Dialog open={open} onClose={handleCancel} maxWidth="sm" fullWidth>
      <DialogTitle>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <DeleteIcon color="error" />
          {title}
        </Box>
      </DialogTitle>
      <DialogContent>
        <Typography variant="body2" sx={{ mb: 1.5 }}>
          {t('selection.bulkDeleteConfirmation', { count: itemNames.length })}
        </Typography>
        {warning ? (
          <Alert severity="warning" icon={<WarningIcon />} sx={{ mb: 1.5 }}>
            {warning}
          </Alert>
        ) : null}
        <List
          dense
          sx={{
            maxHeight: 220,
            overflow: 'auto',
            border: 1,
            borderColor: 'divider',
            borderRadius: 1,
            mb: 1.5,
          }}
        >
          {itemNames.map((name) => (
            <ListItem key={name} disablePadding sx={{ px: 1, py: 0.5 }}>
              <ListItemText
                primary={name}
                primaryTypographyProps={{ variant: 'body2' }}
              />
            </ListItem>
          ))}
        </List>
        <FormControlLabel
          control={
            <Checkbox
              checked={confirmed}
              onChange={(event) => setConfirmed(event.target.checked)}
              disabled={isLoading}
            />
          }
          label={
            <Typography variant="body2">
              {t('selection.confirmBulkDelete')}
            </Typography>
          }
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={handleCancel} disabled={isLoading}>
          {t('actions.cancel')}
        </Button>
        <Button
          color="error"
          variant="contained"
          startIcon={<DeleteIcon />}
          onClick={handleConfirm}
          disabled={isLoading || !confirmed}
        >
          {isLoading ? t('actions.deleting') : t('actions.bulkDelete')}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
