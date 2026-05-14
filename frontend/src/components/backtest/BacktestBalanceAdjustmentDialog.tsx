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
import { useAuth } from '../../contexts/AuthContext';
import { useNumberFormatter } from '../../hooks/useNumberFormatter';
import { formatCurrencyConversionContext } from '../../utils/currencyConversion';
import type { CurrencyConversionContext, MoneyAmount } from '../../types/money';
import { MoneyAmountText } from '../common/MoneyAmountText';

interface BacktestBalanceAdjustmentDialogProps {
  open: boolean;
  currentBalance: number | null;
  accountCurrency: string;
  currentBalanceMoney?: MoneyAmount | null;
  currentBalanceDisplayMoney?: MoneyAmount | null;
  currentBalanceDisplayConversionContext?: CurrencyConversionContext | null;
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
  currentBalanceMoney,
  currentBalanceDisplayMoney,
  currentBalanceDisplayConversionContext,
  isLoading = false,
  onCancel,
  onConfirm,
}: BacktestBalanceAdjustmentDialogProps) {
  const { t } = useTranslation(['backtest', 'common']);
  const { user } = useAuth();
  const { separators } = useNumberFormatter();
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
  const conversionTooltip = formatCurrencyConversionContext(
    currentBalanceDisplayConversionContext,
    {
      language: user?.language,
      separators,
      t,
      timezone: user?.timezone || 'UTC',
    }
  );
  const displayDiffers =
    currentBalanceMoney &&
    currentBalanceDisplayMoney &&
    currentBalanceMoney.currency !== currentBalanceDisplayMoney.currency;

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
              <MoneyAmountText
                money={currentBalanceDisplayMoney ?? currentBalanceMoney}
                fallbackAmount={currentBalance}
                fallbackCurrency={accountCurrency}
                separators={separators}
                tooltip={conversionTooltip}
              />
              {displayDiffers ? (
                <Typography
                  component="span"
                  variant="caption"
                  color="text.secondary"
                  sx={{ ml: 1 }}
                >
                  (
                  <MoneyAmountText
                    money={currentBalanceMoney}
                    fallbackAmount={currentBalance}
                    fallbackCurrency={accountCurrency}
                    separators={separators}
                  />
                  )
                </Typography>
              ) : null}
            </Typography>
          </Box>
          <TextField
            autoFocus
            fullWidth
            label={t('backtest:detail.newCurrentBalanceWithCurrency', {
              currency: accountCurrency,
              defaultValue: `New Current Balance (${accountCurrency})`,
            })}
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
