import { Box, Checkbox, FormControlLabel, Typography } from '@mui/material';
import { useTranslation } from 'react-i18next';

interface DebugOptionsSectionProps {
  tracemalloc: boolean;
  onTracemallocChange: (value: boolean) => void;
  sx?: object;
}

export function DebugOptionsSection({
  tracemalloc,
  onTracemallocChange,
  sx,
}: DebugOptionsSectionProps) {
  const { t } = useTranslation('common');

  return (
    <Box sx={sx}>
      <Typography variant="h6" gutterBottom>
        {t('debug.title')}
      </Typography>
      <FormControlLabel
        control={
          <Checkbox
            checked={tracemalloc}
            onChange={(event) => onTracemallocChange(event.target.checked)}
          />
        }
        label={
          <Box>
            <Typography variant="body1">{t('debug.tracemalloc')}</Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
              {t('debug.tracemallocDescription')}
            </Typography>
          </Box>
        }
      />
    </Box>
  );
}
