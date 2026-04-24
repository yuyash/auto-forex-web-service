import { Box, Typography } from '@mui/material';
import {
  formatSettingValue,
  type TaskSettingValue,
} from './taskSettingsFormat';
import { spacingTokens, typographyTokens } from '../../../theme/density';

export type TaskSettingDefinition<T extends Record<string, unknown>> = {
  key: keyof T & string;
  label: string;
  format?: (value: TaskSettingValue) => string;
};

interface TaskSettingsListProps<T extends Record<string, unknown>> {
  title: string;
  task: T;
  definitions: Array<TaskSettingDefinition<T>>;
  snapshot?: Record<string, unknown> | null;
}

export function TaskSettingsList<T extends Record<string, unknown>>({
  title,
  task,
  definitions,
  snapshot,
}: TaskSettingsListProps<T>) {
  const source = snapshot ?? task;

  return (
    <Box>
      <Typography variant={typographyTokens.subsectionTitle} gutterBottom>
        {title}
      </Typography>
      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: {
            xs: '1fr',
            sm: 'repeat(2, minmax(0, 1fr))',
            lg: 'repeat(3, minmax(0, 1fr))',
          },
          gap: spacingTokens.sm,
        }}
      >
        {definitions.map((definition) => {
          const value = source[definition.key] ?? task[definition.key];
          return (
            <Box key={definition.key} sx={{ minWidth: 0 }}>
              <Typography
                variant={typographyTokens.caption}
                color="text.secondary"
              >
                {definition.label}
              </Typography>
              <Typography
                variant={typographyTokens.body}
                sx={{ wordBreak: 'break-word', whiteSpace: 'pre-wrap' }}
              >
                {definition.format
                  ? definition.format(value as TaskSettingValue)
                  : formatSettingValue(value as TaskSettingValue)}
              </Typography>
            </Box>
          );
        })}
      </Box>
    </Box>
  );
}
