import React from 'react';
import {
  FormControl,
  FormLabel,
  RadioGroup,
  FormControlLabel,
  Radio,
  FormHelperText,
  Box,
  Typography,
} from '@mui/material';
import StorageIcon from '@mui/icons-material/Storage';
import CloudIcon from '@mui/icons-material/Cloud';
import { DataSource } from '../../../types/common';

interface DataSourceSelectorProps {
  value: DataSource;
  onChange: (value: DataSource) => void;
  label?: string;
  required?: boolean;
  disabled?: boolean;
  error?: string;
  helperText?: string;
  showDescriptions?: boolean;
}

const DATA_SOURCE_INFO = {
  [DataSource.POSTGRESQL]: {
    label: 'PostgreSQL',
    description:
      'Use local PostgreSQL database for faster access to recent data',
    icon: StorageIcon,
  },
  [DataSource.ATHENA]: {
    label: 'AWS Athena',
    description:
      'Query historical data from AWS Athena for long-term backtests',
    icon: CloudIcon,
  },
};

export const DataSourceSelector: React.FC<DataSourceSelectorProps> = ({
  value,
  onChange,
  label = 'Data Source',
  required = false,
  disabled = false,
  error,
  helperText,
  showDescriptions = true,
}) => {
  return (
    <FormControl
      component="fieldset"
      error={!!error}
      required={required}
      disabled={disabled}
      fullWidth
    >
      <FormLabel component="legend">{label}</FormLabel>
      <RadioGroup
        value={value}
        onChange={(e) => onChange(e.target.value as DataSource)}
        sx={{ mt: 1 }}
      >
        {Object.entries(DATA_SOURCE_INFO).map(([key, info]) => {
          const Icon = info.icon;
          return (
            <FormControlLabel
              key={key}
              value={key}
              control={<Radio />}
              label={
                showDescriptions ? (
                  <Box
                    sx={{ display: 'flex', alignItems: 'flex-start', py: 0.5 }}
                  >
                    <Icon sx={{ mr: 1.5, mt: 0.5, color: 'action.active' }} />
                    <Box>
                      <Typography variant="body1" sx={{ fontWeight: 500 }}>
                        {info.label}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        {info.description}
                      </Typography>
                    </Box>
                  </Box>
                ) : (
                  <Box sx={{ display: 'flex', alignItems: 'center' }}>
                    <Icon sx={{ mr: 1, color: 'action.active' }} />
                    {info.label}
                  </Box>
                )
              }
              sx={{
                border: 1,
                borderColor: value === key ? 'primary.main' : 'divider',
                borderRadius: 1,
                mb: 1,
                ml: 0,
                mr: 0,
                px: 2,
                py: showDescriptions ? 1 : 0.5,
                '&:hover': {
                  bgcolor: 'action.hover',
                },
              }}
            />
          );
        })}
      </RadioGroup>
      {error && <FormHelperText>{error}</FormHelperText>}
      {!error && helperText && <FormHelperText>{helperText}</FormHelperText>}
    </FormControl>
  );
};
