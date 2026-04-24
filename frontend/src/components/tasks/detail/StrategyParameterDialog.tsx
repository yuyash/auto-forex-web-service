import {
  Box,
  Dialog,
  DialogContent,
  DialogTitle,
  IconButton,
  Typography,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import { isParameterVisible } from '../../../utils/strategySchemaDependsOn';
import { resolveParameterLabel } from '../../../utils/strategySchemaLabels';
import type { ConfigProperty } from '../../../types/strategy';

interface StrategyParameterDialogProps {
  open: boolean;
  onClose: () => void;
  title: string;
  strategyType: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  parameters: Record<string, any>;
  snapshotSchemaProperties?: Record<string, ConfigProperty>;
  paramLabelMap: Record<string, string>;
  labels: {
    strategyType: string;
  };
}

export function StrategyParameterDialog({
  open,
  onClose,
  title,
  strategyType,
  parameters,
  snapshotSchemaProperties,
  paramLabelMap,
  labels,
}: StrategyParameterDialogProps) {
  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        {title}
        <IconButton size="small" onClick={onClose}>
          <CloseIcon fontSize="small" />
        </IconButton>
      </DialogTitle>
      <DialogContent dividers>
        <Typography
          variant="caption"
          color="text.secondary"
          sx={{ mb: 2, display: 'block' }}
        >
          {labels.strategyType}: {strategyType}
        </Typography>
        {Object.entries(parameters || {})
          .filter(([key]) =>
            isParameterVisible(key, parameters || {}, snapshotSchemaProperties)
          )
          .map(([key, value]) => (
            <Box
              key={key}
              sx={{
                display: 'flex',
                justifyContent: 'space-between',
                py: 0.5,
                borderBottom: '1px solid',
                borderColor: 'divider',
              }}
            >
              <Typography variant="body2" color="text.secondary">
                {resolveParameterLabel(paramLabelMap, key)}
              </Typography>
              <Typography
                variant="body2"
                fontWeight={500}
                sx={{ fontFamily: 'monospace' }}
              >
                {typeof value === 'boolean'
                  ? value
                    ? 'true'
                    : 'false'
                  : String(value ?? '-')}
              </Typography>
            </Box>
          ))}
      </DialogContent>
    </Dialog>
  );
}
