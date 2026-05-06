import { useState } from 'react';
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
import { useTranslation } from 'react-i18next';

interface BacktestBalanceAdjustmentDialogProps {
  open: boolean;
  currentBalance: number | null;
  accountCurrency: string;
  isLoading?: boolean;
  onCancel: () => void;
  onConfirm: (data: {
    current_balance: string;
    reason?: string;
  }) => Promise<void>;
}

function parseBalance(value: string): string | null {
  const normalized = value.trim().replace(/,/g, '');
  if (!normalized) return null;
  const parsed = Number(normalized);
  if (!Number.isFinite(parsed) || parsed < 0) return null;
  return normalized;
}

export function BacktestBalanceAdjustmentDialog({
  open,
  currentBalance,
  accountCurrency,
  isLoading = false,
  onCancel,
  onConfirm,
}: BacktestBalanceAdjustmentDialogProps) {
  const { t } = useTranslation(['backtest', 'common']);
  const [balance, setBalance] = useState(() =>
    currentBalance == null ? '' : String(currentBalance)
  );
  const [reason, setReason] = useState('');
  const [error, setError] = useState<string | null>(null);

  const handleConfirm = async () => {
    const parsed = parseBalance(balance);
    if (parsed == null) {
      setError(t('backtest:detail.balanceAdjustmentInvalid'));
      return;
    }
    setError(null);
    await onConfirm({
      current_balance: parsed,
      ...(reason.trim() ? { reason: reason.trim() } : {}),
    });
  };

  return (
    <Dialog
      open={open}
      onClose={isLoading ? undefined : onCancel}
      fullWidth
      maxWidth="xs"
    >
      <DialogTitle>{t('backtest:detail.balanceAdjustmentTitle')}</DialogTitle>
      <DialogContent>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 0.5 }}>
          <Box>
            <Typography variant="caption" color="text.secondary">
              {t('backtest:detail.currentBalance')}
            </Typography>
            <Typography variant="body2" sx={{ fontWeight: 600 }}>
              {currentBalance == null
                ? '-'
                : `${currentBalance} ${accountCurrency}`}
            </Typography>
          </Box>
          <TextField
            autoFocus
            fullWidth
            label={t('backtest:detail.newCurrentBalance')}
            value={balance}
            onChange={(event) => {
              setBalance(event.target.value);
              if (error) setError(null);
            }}
            error={Boolean(error)}
            helperText={error ?? ' '}
            inputProps={{ inputMode: 'decimal' }}
            disabled={isLoading}
          />
          <TextField
            fullWidth
            label={t('backtest:detail.balanceAdjustmentReason')}
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            disabled={isLoading}
          />
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onCancel} disabled={isLoading}>
          {t('common:actions.cancel')}
        </Button>
        <Button
          onClick={handleConfirm}
          variant="contained"
          disabled={isLoading}
        >
          {t('common:actions.ok')}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
