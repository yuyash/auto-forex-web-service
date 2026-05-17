import React from 'react';
import {
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  TextField,
  Typography,
} from '@mui/material';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import { useTranslation } from 'react-i18next';

const MAX_CONFIGURATION_NAME_LENGTH = 100;

interface ConfigurationCopyDialogProps {
  open: boolean;
  configurationName: string;
  isLoading?: boolean;
  apiError?: string;
  onCancel: () => void;
  onConfirm: (newName: string) => void;
  onNameChange?: () => void;
}

export default function ConfigurationCopyDialog({
  open,
  configurationName,
  isLoading = false,
  apiError,
  onCancel,
  onConfirm,
  onNameChange,
}: ConfigurationCopyDialogProps) {
  const { t } = useTranslation(['configuration', 'common']);
  const [newName, setNewName] = React.useState('');
  const [validationError, setValidationError] = React.useState('');

  React.useEffect(() => {
    if (open) {
      setNewName(
        t('configuration:copyDialog.defaultName', {
          name: configurationName,
        })
      );
      setValidationError('');
    }
  }, [configurationName, open, t]);

  const validateAndConfirm = () => {
    const trimmedName = newName.trim();

    if (!trimmedName) {
      setValidationError(t('configuration:validation.nameRequired'));
      return;
    }

    if (trimmedName === configurationName) {
      setValidationError(t('configuration:copyDialog.nameMustDiffer'));
      return;
    }

    if (trimmedName.length > MAX_CONFIGURATION_NAME_LENGTH) {
      setValidationError(t('configuration:validation.nameTooLong'));
      return;
    }

    onConfirm(trimmedName);
  };

  const handleKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === 'Enter' && !isLoading) {
      event.preventDefault();
      validateAndConfirm();
    }
  };

  const helperText =
    validationError ||
    apiError ||
    t('configuration:copyDialog.characterCount', {
      count: newName.length,
      max: MAX_CONFIGURATION_NAME_LENGTH,
    });

  return (
    <Dialog
      open={open}
      onClose={isLoading ? undefined : onCancel}
      maxWidth="sm"
      fullWidth
      aria-labelledby="copy-configuration-dialog-title"
    >
      <DialogTitle id="copy-configuration-dialog-title">
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <ContentCopyIcon />
          {t('configuration:copyDialog.title')}
        </Box>
      </DialogTitle>
      <DialogContent>
        <Box sx={{ pt: 1 }}>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            {t('configuration:copyDialog.description', {
              name: configurationName,
            })}
          </Typography>
          <TextField
            autoFocus
            fullWidth
            required
            label={t('configuration:copyDialog.nameLabel')}
            value={newName}
            onChange={(event) => {
              setNewName(event.target.value);
              setValidationError('');
              onNameChange?.();
            }}
            onKeyDown={handleKeyDown}
            error={!!validationError || !!apiError}
            helperText={helperText}
            disabled={isLoading}
            slotProps={{
              htmlInput: { maxLength: MAX_CONFIGURATION_NAME_LENGTH + 1 },
            }}
          />
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onCancel} disabled={isLoading}>
          {t('common:actions.cancel')}
        </Button>
        <Button
          onClick={validateAndConfirm}
          variant="contained"
          disabled={isLoading || !newName.trim()}
          startIcon={<ContentCopyIcon />}
        >
          {isLoading
            ? t('configuration:copyDialog.copying')
            : t('configuration:copyDialog.confirm')}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
