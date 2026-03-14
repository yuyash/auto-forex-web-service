import {
  Box,
  IconButton,
  Tooltip,
  ToggleButton,
  Typography,
} from '@mui/material';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import SettingsIcon from '@mui/icons-material/Settings';
import SelectAllIcon from '@mui/icons-material/SelectAll';
import DeselectIcon from '@mui/icons-material/Deselect';
import RefreshIcon from '@mui/icons-material/Refresh';
import { useTranslation } from 'react-i18next';

interface TaskTrendSectionHeaderProps {
  title: string;
  count: number;
  selectedCount: number;
  isRefreshing: boolean;
  onConfigureColumns: () => void;
  onCopySelected: () => void;
  onSelectAllOnPage: () => void;
  onResetSelection: () => void;
  onReload: () => void;
  showOpenOnly?: boolean;
  onToggleOpenOnly?: () => void;
}

export function TaskTrendSectionHeader({
  title,
  count,
  selectedCount,
  isRefreshing,
  onConfigureColumns,
  onCopySelected,
  onSelectAllOnPage,
  onResetSelection,
  onReload,
  showOpenOnly,
  onToggleOpenOnly,
}: TaskTrendSectionHeaderProps) {
  const { t } = useTranslation('common');

  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        height: 36,
        minHeight: 36,
      }}
    >
      <Typography variant="subtitle1">{title}</Typography>
      <Typography variant="caption" color="text.secondary" sx={{ ml: 1 }}>
        ({count})
      </Typography>
      {selectedCount > 0 && (
        <Typography variant="caption" color="text.secondary" sx={{ ml: 0.5 }}>
          — {selectedCount} selected
        </Typography>
      )}
      <Box sx={{ flex: 1 }} />
      <Tooltip title={t('common:columnConfig.configureColumns')}>
        <IconButton
          size="small"
          onClick={onConfigureColumns}
          aria-label={t('common:columnConfig.configureColumns')}
        >
          <SettingsIcon fontSize="small" />
        </IconButton>
      </Tooltip>
      <Tooltip title="Copy selected rows">
        <span>
          <IconButton onClick={onCopySelected} disabled={selectedCount === 0}>
            <ContentCopyIcon fontSize="small" />
          </IconButton>
        </span>
      </Tooltip>
      <Tooltip title="Select all on page">
        <IconButton onClick={onSelectAllOnPage}>
          <SelectAllIcon fontSize="small" />
        </IconButton>
      </Tooltip>
      <Tooltip title="Reset selection">
        <span>
          <IconButton onClick={onResetSelection} disabled={selectedCount === 0}>
            <DeselectIcon fontSize="small" />
          </IconButton>
        </span>
      </Tooltip>
      <Tooltip title="Reload data">
        <IconButton onClick={onReload} disabled={isRefreshing}>
          <RefreshIcon fontSize="small" />
        </IconButton>
      </Tooltip>
      {typeof showOpenOnly === 'boolean' && onToggleOpenOnly && (
        <Tooltip title="Show open positions only">
          <ToggleButton
            value="openOnly"
            selected={showOpenOnly}
            onChange={onToggleOpenOnly}
            sx={{
              ml: 1,
              px: 1,
              py: 0,
              height: 24,
              fontSize: '0.7rem',
              textTransform: 'none',
              lineHeight: 1,
            }}
          >
            {t('tables.trend.openOnly')}
          </ToggleButton>
        </Tooltip>
      )}
    </Box>
  );
}
