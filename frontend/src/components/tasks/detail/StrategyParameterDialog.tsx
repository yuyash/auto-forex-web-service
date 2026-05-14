import {
  Box,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  Typography,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { orderConfigEntries } from '../../../utils/configFieldOrder';
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
  paramLabelMap: Map<string, string>;
  labels: {
    strategyType: string;
  };
  actions?: ReactNode;
}

function formatParameterValue(
  value: unknown,
  prop: ConfigProperty | undefined,
  language: string
): string {
  if (value === null || value === undefined || value === '') {
    return '-';
  }

  if (typeof value === 'string') {
    const localizedLabels = prop?.[
      `enum_labels_${language}` as keyof ConfigProperty
    ] as Record<string, string> | undefined;
    const enumLabel = localizedLabels?.[value] ?? prop?.enum_labels?.[value];
    return enumLabel ?? value;
  }

  if (typeof value === 'boolean') {
    return value ? 'true' : 'false';
  }

  if (Array.isArray(value)) {
    return value
      .map((item) => formatParameterValue(item, undefined, language))
      .join(', ');
  }

  if (typeof value === 'object') {
    try {
      return JSON.stringify(value);
    } catch {
      return String(value);
    }
  }

  return String(value);
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
  actions,
}: StrategyParameterDialogProps) {
  const { i18n } = useTranslation();
  const parameterGroups = (() => {
    const groupMap = new Map<string, Array<{ key: string; value: unknown }>>();
    const seenGroups: string[] = [];

    Object.entries(parameters || {})
      .filter(([key]) =>
        isParameterVisible(key, parameters || {}, snapshotSchemaProperties)
      )
      .forEach(([key, value]) => {
        const prop = snapshotSchemaProperties?.[key];
        const localizedGroupKey =
          `group_${i18n.language}` as keyof ConfigProperty;
        const groupName =
          (prop?.[localizedGroupKey] as string | undefined) ??
          prop?.group ??
          '';
        if (!groupMap.has(groupName)) {
          groupMap.set(groupName, []);
          seenGroups.push(groupName);
        }
        groupMap.get(groupName)!.push({ key, value });
      });

    return seenGroups
      .map((name) => ({
        name,
        entries: orderConfigEntries(groupMap.get(name) ?? []),
      }))
      .filter((group) => group.entries.length > 0);
  })();

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
        {parameterGroups.map(({ name: groupName, entries }, groupIdx) => (
          <Box key={groupName || '__ungrouped'} sx={{ mb: 1.5 }}>
            {groupIdx > 0 && (
              <Box sx={{ borderTop: '1px solid', borderColor: 'divider' }} />
            )}
            {groupName && (
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{ display: 'block', fontWeight: 700, mt: 1, mb: 0.5 }}
              >
                {groupName}
              </Typography>
            )}
            {entries.map(({ key, value }) => (
              <Box
                key={key}
                sx={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  gap: 2,
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
                  sx={{
                    fontFamily: 'monospace',
                    textAlign: 'right',
                    wordBreak: 'break-word',
                  }}
                >
                  {formatParameterValue(
                    value,
                    snapshotSchemaProperties?.[key],
                    i18n.language
                  )}
                </Typography>
              </Box>
            ))}
          </Box>
        ))}
      </DialogContent>
      {actions ? <DialogActions>{actions}</DialogActions> : null}
    </Dialog>
  );
}
