import { useState } from 'react';
import {
  Container,
  Paper,
  Typography,
  TextField,
  Button,
  Box,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Alert,
  FormHelperText,
} from '@mui/material';
import Grid from '@mui/material/Grid';
import { useNavigate } from 'react-router-dom';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useAuth } from '../contexts/AuthContext';
import { useAccounts } from '../hooks/useAccounts';
import { Breadcrumbs } from '../components/common';
import { useToast } from '../components/common';

// Validation schema
const orderSchema = z.object({
  account_id: z.number().min(1, 'Account is required'),
  instrument: z.string().min(1, 'Instrument is required'),
  order_type: z.enum(['MARKET', 'LIMIT', 'STOP', 'STOP_LIMIT']),
  direction: z.enum(['BUY', 'SELL']),
  units: z.number().min(1, 'Units must be at least 1'),
  price: z.number().optional(),
  stop_loss: z.number().optional(),
  take_profit: z.number().optional(),
});

type OrderFormData = z.infer<typeof orderSchema>;

const COMMON_INSTRUMENTS = [
  'EUR_USD',
  'GBP_USD',
  'USD_JPY',
  'USD_CHF',
  'AUD_USD',
  'USD_CAD',
  'NZD_USD',
  'EUR_GBP',
  'EUR_JPY',
  'GBP_JPY',
];

export default function CreateOrderPage() {
  const navigate = useNavigate();
  const { token } = useAuth();
  const toast = useToast();
  const [submitting, setSubmitting] = useState(false);

  // Fetch accounts
  const { data: accountsData } = useAccounts({ page_size: 100 });
  const accounts = accountsData?.results || [];

  const {
    control,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<OrderFormData>({
    resolver: zodResolver(orderSchema),
    defaultValues: {
      account_id: 0,
      instrument: '',
      order_type: 'MARKET',
      direction: 'BUY',
      units: 1000,
      price: undefined,
      stop_loss: undefined,
      take_profit: undefined,
    },
  });

  const orderType = watch('order_type');
  const selectedAccountId = watch('account_id');
  const selectedAccount = accounts.find((acc) => acc.id === selectedAccountId);

  const onSubmit = async (data: OrderFormData) => {
    if (!token) return;

    setSubmitting(true);
    try {
      const response = await fetch('/api/orders', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          account_id: data.account_id,
          instrument: data.instrument,
          order_type: data.order_type,
          direction: data.direction,
          units: data.units,
          price: data.price,
          stop_loss: data.stop_loss,
          take_profit: data.take_profit,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to create order');
      }

      toast.showSuccess('Order created successfully');
      navigate('/orders');
    } catch (error) {
      toast.showError(
        error instanceof Error ? error.message : 'Failed to create order'
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Container maxWidth="md">
      <Box sx={{ py: 4 }}>
        <Breadcrumbs />

        <Typography variant="h4" component="h1" gutterBottom>
          Create New Order
        </Typography>

        <Paper sx={{ p: 3, mt: 3 }}>
          <form onSubmit={handleSubmit(onSubmit)}>
            <Grid container spacing={3}>
              {/* Account Selection */}
              <Grid size={{ xs: 12 }}>
                <Controller
                  name="account_id"
                  control={control}
                  render={({ field }) => (
                    <FormControl fullWidth error={!!errors.account_id} required>
                      <InputLabel>Trading Account</InputLabel>
                      <Select
                        {...field}
                        label="Trading Account"
                        value={field.value || ''}
                        onChange={(e) => field.onChange(Number(e.target.value))}
                      >
                        <MenuItem value="">
                          <em>Select an account</em>
                        </MenuItem>
                        {accounts.map((account) => (
                          <MenuItem key={account.id} value={account.id}>
                            {account.account_id} ({account.api_type}) - Balance:
                            ${parseFloat(account.balance).toFixed(2)}
                          </MenuItem>
                        ))}
                      </Select>
                      {errors.account_id && (
                        <FormHelperText>
                          {errors.account_id.message}
                        </FormHelperText>
                      )}
                    </FormControl>
                  )}
                />
              </Grid>

              {/* Live Account Warning */}
              {selectedAccount?.api_type === 'live' && (
                <Grid size={{ xs: 12 }}>
                  <Alert severity="warning">
                    <Typography variant="subtitle2" gutterBottom>
                      <strong>LIVE TRADING WARNING</strong>
                    </Typography>
                    <Typography variant="body2">
                      You are placing an order on a live account. Real money is
                      at risk.
                    </Typography>
                  </Alert>
                </Grid>
              )}

              {/* Instrument */}
              <Grid size={{ xs: 12, sm: 6 }}>
                <Controller
                  name="instrument"
                  control={control}
                  render={({ field }) => (
                    <FormControl fullWidth error={!!errors.instrument} required>
                      <InputLabel>Instrument</InputLabel>
                      <Select {...field} label="Instrument">
                        <MenuItem value="">
                          <em>Select instrument</em>
                        </MenuItem>
                        {COMMON_INSTRUMENTS.map((instrument) => (
                          <MenuItem key={instrument} value={instrument}>
                            {instrument}
                          </MenuItem>
                        ))}
                      </Select>
                      {errors.instrument && (
                        <FormHelperText>
                          {errors.instrument.message}
                        </FormHelperText>
                      )}
                    </FormControl>
                  )}
                />
              </Grid>

              {/* Order Type */}
              <Grid size={{ xs: 12, sm: 6 }}>
                <Controller
                  name="order_type"
                  control={control}
                  render={({ field }) => (
                    <FormControl fullWidth required>
                      <InputLabel>Order Type</InputLabel>
                      <Select {...field} label="Order Type">
                        <MenuItem value="MARKET">Market</MenuItem>
                        <MenuItem value="LIMIT">Limit</MenuItem>
                        <MenuItem value="STOP">Stop</MenuItem>
                        <MenuItem value="STOP_LIMIT">Stop Limit</MenuItem>
                      </Select>
                    </FormControl>
                  )}
                />
              </Grid>

              {/* Direction */}
              <Grid size={{ xs: 12, sm: 6 }}>
                <Controller
                  name="direction"
                  control={control}
                  render={({ field }) => (
                    <FormControl fullWidth required>
                      <InputLabel>Direction</InputLabel>
                      <Select {...field} label="Direction">
                        <MenuItem value="BUY">Buy</MenuItem>
                        <MenuItem value="SELL">Sell</MenuItem>
                      </Select>
                    </FormControl>
                  )}
                />
              </Grid>

              {/* Units */}
              <Grid size={{ xs: 12, sm: 6 }}>
                <Controller
                  name="units"
                  control={control}
                  render={({ field }) => (
                    <TextField
                      {...field}
                      fullWidth
                      label="Units"
                      type="number"
                      required
                      error={!!errors.units}
                      helperText={errors.units?.message}
                      onChange={(e) => field.onChange(Number(e.target.value))}
                    />
                  )}
                />
              </Grid>

              {/* Price (for LIMIT and STOP_LIMIT orders) */}
              {(orderType === 'LIMIT' || orderType === 'STOP_LIMIT') && (
                <Grid size={{ xs: 12, sm: 6 }}>
                  <Controller
                    name="price"
                    control={control}
                    render={({ field }) => (
                      <TextField
                        {...field}
                        fullWidth
                        label="Price"
                        type="number"
                        inputProps={{ step: '0.00001' }}
                        error={!!errors.price}
                        helperText={errors.price?.message}
                        onChange={(e) =>
                          field.onChange(
                            e.target.value ? Number(e.target.value) : undefined
                          )
                        }
                      />
                    )}
                  />
                </Grid>
              )}

              {/* Stop Loss */}
              <Grid size={{ xs: 12, sm: 6 }}>
                <Controller
                  name="stop_loss"
                  control={control}
                  render={({ field }) => (
                    <TextField
                      {...field}
                      fullWidth
                      label="Stop Loss (Optional)"
                      type="number"
                      inputProps={{ step: '0.00001' }}
                      error={!!errors.stop_loss}
                      helperText={errors.stop_loss?.message}
                      onChange={(e) =>
                        field.onChange(
                          e.target.value ? Number(e.target.value) : undefined
                        )
                      }
                    />
                  )}
                />
              </Grid>

              {/* Take Profit */}
              <Grid size={{ xs: 12, sm: 6 }}>
                <Controller
                  name="take_profit"
                  control={control}
                  render={({ field }) => (
                    <TextField
                      {...field}
                      fullWidth
                      label="Take Profit (Optional)"
                      type="number"
                      inputProps={{ step: '0.00001' }}
                      error={!!errors.take_profit}
                      helperText={errors.take_profit?.message}
                      onChange={(e) =>
                        field.onChange(
                          e.target.value ? Number(e.target.value) : undefined
                        )
                      }
                    />
                  )}
                />
              </Grid>

              {/* Action Buttons */}
              <Grid size={{ xs: 12 }}>
                <Box
                  sx={{ display: 'flex', gap: 2, justifyContent: 'flex-end' }}
                >
                  <Button
                    variant="outlined"
                    onClick={() => navigate('/orders')}
                    disabled={submitting}
                  >
                    Cancel
                  </Button>
                  <Button
                    type="submit"
                    variant="contained"
                    disabled={submitting}
                  >
                    {submitting ? 'Creating...' : 'Create Order'}
                  </Button>
                </Box>
              </Grid>
            </Grid>
          </form>
        </Paper>
      </Box>
    </Container>
  );
}
