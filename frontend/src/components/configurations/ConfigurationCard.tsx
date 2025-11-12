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
} from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import FolderIcon from '@mui/icons-material/Folder';
import { useNavigate } from 'react-router-dom';
import type { StrategyConfig } from '../../types/configuration';
import ConfigurationDeleteDialog from './ConfigurationDeleteDialog';
import {
  useStrategies,
  getStrategyDisplayName,
} from '../../hooks/useStrategies';

interface ConfigurationCardProps {
  configuration: StrategyConfig;
}

const ConfigurationCard = ({ configuration }: ConfigurationCardProps) => {
  const navigate = useNavigate();
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const menuOpen = Boolean(anchorEl);
  const { strategies } = useStrategies();

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

  const getDisplayName = (strategyId: string) => {
    return getStrategyDisplayName(strategies, strategyId);
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  // Count parameters
  const parameterCount = configuration.parameters
    ? Object.keys(configuration.parameters).length
    : 0;

  return (
    <>
      <Card
        elevation={2}
        sx={{
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          transition: 'all 0.2s ease-in-out',
          '&:hover': {
            transform: 'translateY(-4px)',
            boxShadow: 4,
          },
        }}
      >
        <CardContent sx={{ flexGrow: 1 }}>
          {/* Header with name and menu */}
          <Box
            sx={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'flex-start',
              mb: 2,
            }}
          >
            <Typography
              variant="h6"
              component="div"
              sx={{
                fontWeight: 600,
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
              size="small"
              onClick={handleMenuOpen}
              sx={{ mt: -1, mr: -1 }}
            >
              <MoreVertIcon />
            </IconButton>
          </Box>

          {/* Strategy Type */}
          <Box sx={{ mb: 2 }}>
            <Chip
              label={getDisplayName(configuration.strategy_type)}
              color="primary"
              size="small"
              variant="outlined"
            />
          </Box>

          {/* Description */}
          {configuration.description && (
            <Typography
              variant="body2"
              color="text.secondary"
              sx={{
                mb: 2,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                display: '-webkit-box',
                WebkitLineClamp: 2,
                WebkitBoxOrient: 'vertical',
                minHeight: '2.5em',
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
              gap: 1,
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
                Parameters
              </Typography>
              <Typography variant="caption" fontWeight={500}>
                {parameterCount}
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
              <Box sx={{ mt: 1 }}>
                <Chip
                  label="In Use"
                  color="success"
                  size="small"
                  variant="filled"
                  sx={{ fontSize: '0.7rem' }}
                />
              </Box>
            )}
          </Box>
        </CardContent>

        <CardActions sx={{ px: 2, pb: 2, pt: 0 }}>
          <Tooltip title="Edit Configuration">
            <IconButton
              size="small"
              color="primary"
              onClick={handleEdit}
              sx={{ mr: 1 }}
            >
              <EditIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title="Delete Configuration">
            <IconButton
              size="small"
              color="error"
              onClick={handleDelete}
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
        <MenuItem onClick={handleEdit}>
          <ListItemIcon>
            <EditIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText>Edit</ListItemText>
        </MenuItem>
        <MenuItem onClick={handleViewTasks}>
          <ListItemIcon>
            <FolderIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText>View Tasks</ListItemText>
        </MenuItem>
        <MenuItem onClick={handleDelete} disabled={configuration.is_in_use}>
          <ListItemIcon>
            <DeleteIcon
              fontSize="small"
              color={configuration.is_in_use ? 'disabled' : 'error'}
            />
          </ListItemIcon>
          <ListItemText>Delete</ListItemText>
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
