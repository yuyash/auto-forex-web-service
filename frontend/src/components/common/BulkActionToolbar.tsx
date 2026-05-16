import { Box, Button, Chip, Paper, Tooltip, Typography } from '@mui/material';
import {
  CheckBox as SelectAllIcon,
  CheckBoxOutlineBlank as ClearSelectionIcon,
  CompareArrows as CompareArrowsIcon,
  ContentCopy as CopyIcon,
  Delete as DeleteIcon,
  Edit as EditIcon,
} from '@mui/icons-material';
import { useTranslation } from 'react-i18next';
import type { ReactElement } from 'react';

interface BulkActionToolbarProps {
  selectedCount: number;
  totalCount: number;
  onSelectAll: () => void;
  onClearSelection: () => void;
  onBulkDelete: () => void;
  onCopy: () => void;
  onEdit: () => void;
  onCompare?: () => void;
  disableBulkDelete?: boolean;
  bulkDeleteTooltip?: string;
  disableCopy?: boolean;
  copyTooltip?: string;
  disableEdit?: boolean;
  editTooltip?: string;
  disableCompare?: boolean;
}

export function BulkActionToolbar({
  selectedCount,
  totalCount,
  onSelectAll,
  onClearSelection,
  onBulkDelete,
  onCopy,
  onEdit,
  onCompare,
  disableBulkDelete = false,
  bulkDeleteTooltip,
  disableCopy = false,
  copyTooltip,
  disableEdit = false,
  editTooltip,
  disableCompare = false,
}: BulkActionToolbarProps) {
  const { t } = useTranslation('common');
  const hasSelection = selectedCount > 0;

  const wrapTooltip = (label: string | undefined, child: ReactElement) => (
    <Tooltip title={label ?? ''} disableHoverListener={!label}>
      <span>{child}</span>
    </Tooltip>
  );

  return (
    <Paper
      variant="outlined"
      sx={{
        p: 1,
        mb: 1,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 1,
        flexWrap: 'wrap',
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
        <Chip
          size="small"
          color={hasSelection ? 'primary' : 'default'}
          variant={hasSelection ? 'filled' : 'outlined'}
          label={t('selection.selectedCount', {
            selected: selectedCount,
            total: totalCount,
          })}
        />
        <Typography variant="caption" color="text.secondary">
          {t('selection.visibleItems', { count: totalCount })}
        </Typography>
      </Box>

      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 0.75,
          flexWrap: 'wrap',
          '& .MuiButton-root': {
            minWidth: 0,
            px: { xs: 0.75, sm: 1 },
            whiteSpace: 'nowrap',
          },
        }}
      >
        <Button
          size="small"
          variant="outlined"
          startIcon={<SelectAllIcon />}
          onClick={onSelectAll}
          disabled={totalCount === 0 || selectedCount === totalCount}
        >
          {t('actions.selectAll')}
        </Button>
        <Button
          size="small"
          variant="outlined"
          startIcon={<ClearSelectionIcon />}
          onClick={onClearSelection}
          disabled={!hasSelection}
        >
          {t('actions.clearSelection')}
        </Button>
        {onCompare && (
          <Button
            size="small"
            variant="outlined"
            startIcon={<CompareArrowsIcon />}
            disabled={disableCompare}
            onClick={onCompare}
          >
            {t('actions.compare')}
          </Button>
        )}
        {wrapTooltip(
          copyTooltip,
          <Button
            size="small"
            variant="outlined"
            startIcon={<CopyIcon />}
            disabled={disableCopy}
            onClick={onCopy}
          >
            {t('actions.copy')}
          </Button>
        )}
        {wrapTooltip(
          editTooltip,
          <Button
            size="small"
            variant="outlined"
            startIcon={<EditIcon />}
            disabled={disableEdit}
            onClick={onEdit}
          >
            {t('actions.edit')}
          </Button>
        )}
        {wrapTooltip(
          bulkDeleteTooltip,
          <Button
            size="small"
            variant="outlined"
            color="error"
            startIcon={<DeleteIcon />}
            disabled={disableBulkDelete}
            onClick={onBulkDelete}
          >
            {t('actions.bulkDelete')}
          </Button>
        )}
      </Box>
    </Paper>
  );
}
