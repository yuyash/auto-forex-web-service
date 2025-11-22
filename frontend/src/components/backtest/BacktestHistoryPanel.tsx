import { useState } from 'react';
import {
  Box,
  Paper,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  IconButton,
  Tooltip,
  Alert,
  Chip,
  // Button, // TODO: Uncomment when comparison modal is reimplemented
} from '@mui/material';
import { useTranslation } from 'react-i18next';
import VisibilityIcon from '@mui/icons-material/Visibility';
import DeleteIcon from '@mui/icons-material/Delete';
// import CompareArrowsIcon from '@mui/icons-material/CompareArrows'; // TODO: Uncomment when comparison modal is reimplemented
import type { Backtest, BacktestResult } from '../../types/backtest';
// import BacktestComparisonModal from './BacktestComparisonModal'; // TODO: Reimplement with react-financial-charts

interface BacktestHistoryPanelProps {
  backtests: Backtest[];
  onViewBacktest: (backtestId: number) => void;
  onDeleteBacktest: (backtestId: number) => void;
  onFetchResult?: (backtestId: number) => Promise<BacktestResult>; // Optional until comparison modal is reimplemented
  loading?: boolean;
}

const BacktestHistoryPanel = ({
  backtests,
  onViewBacktest,
  onDeleteBacktest,
  // onFetchResult, // TODO: Uncomment when comparison modal is reimplemented
  loading = false,
}: BacktestHistoryPanelProps) => {
  const { t } = useTranslation(['backtest', 'common']);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  // const [comparisonModalOpen, setComparisonModalOpen] = useState(false); // TODO: Uncomment when comparison modal is reimplemented

  // Format date for display
  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  // Format date range
  const formatDateRange = (startDate: string, endDate: string) => {
    return `${formatDate(startDate)} - ${formatDate(endDate)}`;
  };

  // Get status color
  const getStatusColor = (
    status: string
  ): 'default' | 'primary' | 'success' | 'error' | 'warning' => {
    switch (status) {
      case 'completed':
        return 'success';
      case 'running':
        return 'primary';
      case 'failed':
        return 'error';
      case 'pending':
        return 'warning';
      default:
        return 'default';
    }
  };

  // Handle delete with confirmation
  const handleDelete = async (backtestId: number) => {
    if (
      !window.confirm(
        t(
          'backtest:history.deleteConfirm',
          'Are you sure you want to delete this backtest?'
        )
      )
    ) {
      return;
    }

    setDeletingId(backtestId);
    try {
      await onDeleteBacktest(backtestId);
    } finally {
      setDeletingId(null);
    }
  };

  // Calculate total return if available
  const calculateTotalReturn = (backtest: Backtest) => {
    // This would typically come from the backtest result
    // For now, we'll show N/A for non-completed backtests
    if (backtest.status !== 'completed') {
      return 'N/A';
    }
    // In a real implementation, this would be fetched from the result
    return 'View Results';
  };

  if (backtests.length === 0) {
    return (
      <Alert severity="info">
        {t(
          'backtest:history.noBacktests',
          'No backtest history available. Run a backtest to see it here.'
        )}
      </Alert>
    );
  }

  // const completedBacktests = backtests.filter(
  //   (bt) => bt.status === 'completed'
  // ); // TODO: Uncomment when comparison modal is reimplemented

  return (
    <Box>
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          mb: 2,
        }}
      >
        <Typography variant="h6">
          {t('backtest:history.title', 'Backtest History')}
        </Typography>
        {/* TODO: Reimplement comparison feature with react-financial-charts */}
        {/* <Button
          variant="outlined"
          startIcon={<CompareArrowsIcon />}
          onClick={() => setComparisonModalOpen(true)}
          disabled={completedBacktests.length < 2}
        >
          {t('backtest:history.compareBacktests', 'Compare Backtests')}
        </Button> */}
      </Box>

      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>{t('backtest:history.date', 'Date')}</TableCell>
              <TableCell>
                {t('backtest:history.strategy', 'Strategy')}
              </TableCell>
              <TableCell>
                {t('backtest:history.instrument', 'Instrument')}
              </TableCell>
              <TableCell>
                {t('backtest:history.dateRange', 'Date Range')}
              </TableCell>
              <TableCell>{t('backtest:history.status', 'Status')}</TableCell>
              <TableCell>
                {t('backtest:history.totalReturn', 'Total Return')}
              </TableCell>
              <TableCell align="right">
                {t('backtest:history.actions', 'Actions')}
              </TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {backtests.map((backtest) => (
              <TableRow
                key={backtest.id}
                sx={{
                  '&:hover': {
                    backgroundColor: 'action.hover',
                  },
                }}
              >
                <TableCell>{formatDate(backtest.created_at)}</TableCell>
                <TableCell>
                  <Typography variant="body2" fontWeight="medium">
                    {backtest.strategy_type}
                  </Typography>
                </TableCell>
                <TableCell>
                  <Chip
                    label={backtest.instrument}
                    size="small"
                    variant="outlined"
                  />
                </TableCell>
                <TableCell>
                  <Typography variant="body2" noWrap>
                    {formatDateRange(backtest.start_date, backtest.end_date)}
                  </Typography>
                </TableCell>
                <TableCell>
                  <Chip
                    label={t(
                      `backtest:progress.statusValues.${backtest.status}`,
                      backtest.status
                    )}
                    color={getStatusColor(backtest.status)}
                    size="small"
                  />
                </TableCell>
                <TableCell>
                  <Typography variant="body2">
                    {calculateTotalReturn(backtest)}
                  </Typography>
                </TableCell>
                <TableCell align="right">
                  <Tooltip
                    title={t('backtest:history.viewResults', 'View Results')}
                  >
                    <span>
                      <IconButton
                        size="small"
                        onClick={() => onViewBacktest(backtest.id)}
                        disabled={backtest.status !== 'completed' || loading}
                        color="primary"
                        aria-label={t(
                          'backtest:history.viewResults',
                          'View Results'
                        )}
                      >
                        <VisibilityIcon fontSize="small" />
                      </IconButton>
                    </span>
                  </Tooltip>
                  <Tooltip title={t('backtest:history.delete', 'Delete')}>
                    <span>
                      <IconButton
                        size="small"
                        onClick={() => handleDelete(backtest.id)}
                        disabled={deletingId === backtest.id || loading}
                        color="error"
                        aria-label={t('backtest:history.delete', 'Delete')}
                      >
                        <DeleteIcon fontSize="small" />
                      </IconButton>
                    </span>
                  </Tooltip>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      {/* TODO: Reimplement BacktestComparisonModal with react-financial-charts */}
      {/* <BacktestComparisonModal
        open={comparisonModalOpen}
        onClose={() => setComparisonModalOpen(false)}
        backtests={backtests}
        onFetchResult={onFetchResult}
      /> */}
    </Box>
  );
};

export default BacktestHistoryPanel;
