import type { ReactNode } from 'react';
import {
  Box,
  IconButton,
  Paper,
  Tooltip,
  Typography,
  type IconButtonProps,
} from '@mui/material';
import { Delete as DeleteIcon, Edit as EditIcon } from '@mui/icons-material';
import { formatInTimeZone } from 'date-fns-tz';
import { TaskControlButtons } from '../../common/TaskControlButtons';
import { StatusBadge } from '../display/StatusBadge';
import { type TickInfo } from '../../../hooks/useTaskSummary';
import { TaskStatus } from '../../../types/common';

interface TaskDetailHeaderProps {
  taskId: string;
  taskName: string;
  taskDescription?: string;
  taskStatus: TaskStatus;
  currentStatus?: TaskStatus;
  strategyName: string;
  instrument: string;
  pipSize?: string;
  tick: TickInfo;
  timezone: string;
  isMobile: boolean;
  progress: number;
  completedLabel: string;
  editLabel: string;
  deleteLabel: string;
  onStart: (id: string) => Promise<void>;
  onStop: (id: string) => Promise<void>;
  onRestart: (id: string) => Promise<void>;
  onResume: (id: string) => Promise<void>;
  onPause: (id: string) => Promise<void>;
  onEdit: () => void;
  onDelete: () => void;
}

function buildTickText(tick: TickInfo, pipSize?: string) {
  const decimals = pipSize ? String(pipSize).split('.')[1]?.length || 5 : 5;

  return {
    decimals,
    mid: tick.mid?.toFixed(decimals),
    bid: tick.bid?.toFixed(decimals),
    ask: tick.ask?.toFixed(decimals),
    spread:
      tick.ask != null && tick.bid != null
        ? (tick.ask - tick.bid).toFixed(decimals)
        : null,
  };
}

function ActionButton({
  title,
  disabled,
  color,
  size,
  ariaLabel,
  onClick,
  children,
}: {
  title: string;
  disabled: boolean;
  color?: IconButtonProps['color'];
  size: IconButtonProps['size'];
  ariaLabel: string;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <Tooltip title={title}>
      <span>
        <IconButton
          size={size}
          onClick={onClick}
          disabled={disabled}
          color={color}
          aria-label={ariaLabel}
        >
          {children}
        </IconButton>
      </span>
    </Tooltip>
  );
}

export function TaskDetailHeader({
  taskId,
  taskName,
  taskDescription,
  taskStatus,
  currentStatus,
  strategyName,
  instrument,
  pipSize,
  tick,
  timezone,
  isMobile,
  progress,
  completedLabel,
  editLabel,
  deleteLabel,
  onStart,
  onStop,
  onRestart,
  onResume,
  onPause,
  onEdit,
  onDelete,
}: TaskDetailHeaderProps) {
  const status = currentStatus || taskStatus;
  const actionDisabled =
    status === TaskStatus.RUNNING || status === TaskStatus.PAUSED;
  const tickText = buildTickText(tick, pipSize);

  return (
    <Paper sx={{ p: { xs: 1.5, sm: 2 }, pb: 1, mb: { xs: 1, sm: 2 } }}>
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 1,
            p: '4px',
            flexWrap: 'wrap',
          }}
        >
          <Typography
            variant="h4"
            component="h1"
            sx={{
              fontSize: { xs: '1.25rem', sm: '2.125rem' },
              wordBreak: 'break-word',
              flex: 1,
              minWidth: 0,
            }}
          >
            {taskName}
          </Typography>
          <StatusBadge status={status} />
        </Box>

        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 1,
            pl: '4px',
            flexWrap: 'wrap',
          }}
        >
          <TaskControlButtons
            taskId={taskId}
            status={status}
            onStart={onStart}
            onStop={onStop}
            onRestart={onRestart}
            onResume={onResume}
            onPause={onPause}
          />
          <ActionButton
            title={editLabel}
            disabled={actionDisabled}
            size={isMobile ? 'small' : 'medium'}
            ariaLabel={editLabel}
            onClick={onEdit}
          >
            <EditIcon />
          </ActionButton>
          <ActionButton
            title={deleteLabel}
            disabled={actionDisabled}
            size={isMobile ? 'small' : 'medium'}
            color="error"
            ariaLabel={deleteLabel}
            onClick={onDelete}
          >
            <DeleteIcon />
          </ActionButton>
        </Box>

        <Typography variant="body2" color="text.secondary" sx={{ pl: '4px' }}>
          {strategyName}
        </Typography>

        {taskDescription && (
          <Typography variant="body2" color="text.secondary" sx={{ pl: '4px' }}>
            {taskDescription}
          </Typography>
        )}

        {tick.mid != null && (
          <Box
            sx={{
              display: 'flex',
              flexWrap: 'wrap',
              alignItems: 'center',
              gap: { xs: 0.5, sm: 1 },
              pl: '4px',
              rowGap: 0.25,
              fontSize: { xs: '0.7rem', sm: '0.875rem' },
            }}
          >
            <Typography
              variant="body2"
              color="text.secondary"
              component="span"
              sx={{ fontSize: 'inherit' }}
            >
              {instrument}:
            </Typography>
            <Typography
              variant="caption"
              color="text.secondary"
              component="span"
              sx={{ fontFamily: 'monospace', fontSize: 'inherit' }}
            >
              Mid {tickText.mid}
            </Typography>
            {tickText.bid != null &&
              tickText.ask != null &&
              tickText.spread && (
                <>
                  <Typography
                    variant="caption"
                    color="text.secondary"
                    component="span"
                    sx={{ fontFamily: 'monospace', fontSize: 'inherit' }}
                  >
                    Bid {tickText.bid}
                  </Typography>
                  <Typography
                    variant="caption"
                    color="text.secondary"
                    component="span"
                    sx={{ fontFamily: 'monospace', fontSize: 'inherit' }}
                  >
                    Ask {tickText.ask}
                  </Typography>
                  <Typography
                    variant="caption"
                    color="text.secondary"
                    component="span"
                    sx={{ fontFamily: 'monospace', fontSize: 'inherit' }}
                  >
                    Spd {tickText.spread}
                  </Typography>
                </>
              )}
            {tick.timestamp && (
              <Typography
                variant="caption"
                color="text.secondary"
                component="span"
                sx={{ fontFamily: 'monospace', fontSize: 'inherit' }}
              >
                @{' '}
                {formatInTimeZone(
                  new Date(tick.timestamp),
                  timezone,
                  'yyyy-MM-dd HH:mm:ss zzz'
                )}
              </Typography>
            )}
          </Box>
        )}

        {status === TaskStatus.RUNNING && (
          <Typography
            variant="body2"
            color="text.secondary"
            sx={{ pl: '4px', fontWeight: 600 }}
          >
            {Math.round(Math.min(Math.max(progress, 0), 100))}% {completedLabel}
          </Typography>
        )}
      </Box>
    </Paper>
  );
}
