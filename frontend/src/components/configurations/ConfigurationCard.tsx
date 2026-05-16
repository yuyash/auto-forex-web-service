import { useState } from 'react';
import {
  Card,
  CardContent,
  CardActions,
  Typography,
  Box,
  Chip,
  IconButton,
  Tooltip,
  Menu,
  MenuItem,
  ListItemIcon,
  ListItemText,
  Checkbox,
} from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import FolderIcon from '@mui/icons-material/Folder';
import { useNavigate } from 'react-router-dom';
import type { StrategyConfig } from '../../types/configuration';
import ConfigurationDeleteDialog from './ConfigurationDeleteDialog';
import {
  useStrategies,
  getStrategyDisplayName,
} from '../../hooks/useStrategies';
import { useCopyConfiguration } from '../../hooks/useConfigurationMutations';
import { useTranslation } from 'react-i18next';
import { useDateTimeFormatter } from '../../hooks/useDateTimeFormatter';

interface ConfigurationCardProps {
  configuration: StrategyConfig;
  selected?: boolean;
  onSelectedChange?: (id: string, selected: boolean) => void;
}

const ConfigurationCard = ({
  configuration,
  selected = false,
  onSelectedChange,
}: ConfigurationCardProps) => {
  const { t } = useTranslation(['configuration', 'common']);
  const { formatDate } = useDateTimeFormatter();
  const navigate = useNavigate();
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const menuOpen = Boolean(anchorEl);
  const { strategies } = useStrategies();
  const copyMutation = useCopyConfiguration({
    onSuccess: (copied) => {
      navigate(`/configurations/${copied.id}`);
    },
  });
  const editDisabled = configuration.has_running_tasks;
  const editTooltip = editDisabled
    ? t('configuration:form.editLockedRunningTasks')
    : t('configuration:card.editConfiguration');

  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
  };

  const handleEdit = () => {
    handleMenuClose();
    navigate(`/configurations/${configuration.id}/edit`);
  };

  const handleDelete = () => {
    handleMenuClose();
    setDeleteDialogOpen(true);
  };

  const handleViewTasks = () => {
    handleMenuClose();
    // Navigate to tasks page filtered by this configuration
    navigate(`/backtest-tasks?config=${configuration.id}`);
  };

  const handleCopy = () => {
    handleMenuClose();
    copyMutation.mutate({ id: configuration.id });
  };

  const handleOpenDetail = () => {
    navigate(`/configurations/${configuration.id}`);
  };

  const getDisplayName = (strategyId: string) => {
    return getStrategyDisplayName(strategies, strategyId);
  };

  return (
    <>
      <Card
        elevation={2}
        onClick={handleOpenDetail}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            handleOpenDetail();
          }
        }}
        sx={{
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          cursor: 'pointer',
          transition: 'all 0.2s ease-in-out',
          outline: selected ? '2px solid' : '2px solid transparent',
          outlineColor: selected ? 'primary.main' : 'transparent',
          outlineOffset: 0,
          '&:hover': {
            transform: 'translateY(-4px)',
            boxShadow: 4,
          },
        }}
      >
        <CardContent
          sx={{
            flexGrow: 1,
            p: { xs: 1, sm: 1.25 },
            '&:last-child': { pb: { xs: 1, sm: 1.25 } },
          }}
        >
          {/* Header with name and menu */}
          <Box
            sx={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'flex-start',
              mb: 0.75,
            }}
          >
            {onSelectedChange && (
              <Tooltip
                title={t('common:actions.selectForCompare', {
                  defaultValue: 'Select for comparison',
                })}
              >
                <Checkbox
                  checked={selected}
                  onChange={(event) => {
                    event.stopPropagation();
                    onSelectedChange(configuration.id, event.target.checked);
                  }}
                  onClick={(event) => event.stopPropagation()}
                  onKeyDown={(event) => event.stopPropagation()}
                  inputProps={{
                    'aria-label': t('common:actions.selectForCompare', {
                      defaultValue: 'Select for comparison',
                    }),
                  }}
                  size="small"
                  sx={{ p: 0.25, mr: 0.75, mt: -0.25 }}
                />
              </Tooltip>
            )}
            <Typography
              variant="subtitle1"
              component="div"
              sx={{
                fontWeight: 600,
                lineHeight: 1.25,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                display: '-webkit-box',
                WebkitLineClamp: 2,
                WebkitBoxOrient: 'vertical',
                flex: 1,
                mr: 1,
              }}
            >
              {configuration.name}
            </Typography>
            <IconButton
              onClick={(e) => {
                e.stopPropagation();
                handleMenuOpen(e);
              }}
              sx={{ mt: -0.5, mr: -0.5 }}
            >
              <MoreVertIcon />
            </IconButton>
          </Box>

          {/* Strategy Type */}
          <Box sx={{ mb: 0.75 }}>
            <Chip
              label={getDisplayName(configuration.strategy_type)}
              color="primary"
              variant="outlined"
              size="small"
            />
          </Box>

          {/* Description */}
          {configuration.description && (
            <Typography
              variant="body2"
              color="text.secondary"
              sx={{
                mb: 0.75,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                display: '-webkit-box',
                WebkitLineClamp: 1,
                WebkitBoxOrient: 'vertical',
              }}
            >
              {configuration.description}
            </Typography>
          )}

          {/* Metadata */}
          <Box
            sx={{
              display: 'flex',
              flexDirection: 'column',
              gap: 0.5,
              mt: 'auto',
            }}
          >
            <Box
              sx={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
              }}
            >
              <Typography variant="caption" color="text.secondary">
                {t('configuration:card.revision')}
              </Typography>
              <Typography variant="caption" fontWeight={500}>
                Rev.{configuration.revision}
              </Typography>
            </Box>
            <Box
              sx={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
              }}
            >
              <Typography variant="caption" color="text.secondary">
                Created
              </Typography>
              <Typography variant="caption" fontWeight={500}>
                {formatDate(configuration.created_at)}
              </Typography>
            </Box>
            {configuration.is_in_use && (
              <Box sx={{ mt: 0.25 }}>
                <Chip
                  label={t('common:labels.inUse')}
                  color="success"
                  variant="filled"
                  sx={{ fontSize: '0.7rem' }}
                />
              </Box>
            )}
          </Box>
        </CardContent>

        <CardActions sx={{ px: { xs: 1, sm: 1.25 }, pb: 1, pt: 0 }}>
          <Tooltip title={editTooltip}>
            <IconButton
              color="primary"
              onClick={(e) => {
                e.stopPropagation();
                handleEdit();
              }}
              disabled={editDisabled}
              sx={{ mr: 0.5 }}
            >
              <EditIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title={t('common:actions.copy')}>
            <IconButton
              onClick={(e) => {
                e.stopPropagation();
                handleCopy();
              }}
              sx={{ mr: 0.5 }}
            >
              <ContentCopyIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title={t('configuration:card.deleteConfiguration')}>
            <IconButton
              color="error"
              onClick={(e) => {
                e.stopPropagation();
                handleDelete();
              }}
              disabled={configuration.is_in_use}
            >
              <DeleteIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </CardActions>
      </Card>

      {/* Action Menu */}
      <Menu
        anchorEl={anchorEl}
        open={menuOpen}
        onClose={handleMenuClose}
        anchorOrigin={{
          vertical: 'top',
          horizontal: 'right',
        }}
        transformOrigin={{
          vertical: 'top',
          horizontal: 'right',
        }}
      >
        <MenuItem onClick={handleEdit} disabled={editDisabled}>
          <ListItemIcon>
            <EditIcon
              fontSize="small"
              color={editDisabled ? 'disabled' : 'inherit'}
            />
          </ListItemIcon>
          <ListItemText>{t('common:actions.edit')}</ListItemText>
        </MenuItem>
        <MenuItem onClick={handleViewTasks}>
          <ListItemIcon>
            <FolderIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText>{t('common:actions.viewTasks')}</ListItemText>
        </MenuItem>
        <MenuItem onClick={handleCopy}>
          <ListItemIcon>
            <ContentCopyIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText>{t('common:actions.copy')}</ListItemText>
        </MenuItem>
        <MenuItem onClick={handleDelete} disabled={configuration.is_in_use}>
          <ListItemIcon>
            <DeleteIcon
              fontSize="small"
              color={configuration.is_in_use ? 'disabled' : 'error'}
            />
          </ListItemIcon>
          <ListItemText>{t('common:actions.delete')}</ListItemText>
        </MenuItem>
      </Menu>

      {/* Delete Dialog */}
      <ConfigurationDeleteDialog
        open={deleteDialogOpen}
        configuration={configuration}
        onClose={() => setDeleteDialogOpen(false)}
      />
    </>
  );
};

export default ConfigurationCard;
