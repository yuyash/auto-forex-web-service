import { useState, type ReactNode } from 'react';
import {
  Box,
  Collapse,
  IconButton,
  Paper,
  Tooltip,
  Typography,
  type IconButtonProps,
} from '@mui/material';
import {
  Delete as DeleteIcon,
  Edit as EditIcon,
  ExpandLess as ExpandLessIcon,
  ExpandMore as ExpandMoreIcon,
} from '@mui/icons-material';
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
  showProgress?: boolean;
  currentAtr?: number | null;
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
  const pipSizeNum = pipSize ? parseFloat(pipSize) : 0.01;

  return {
    mid: tick.mid?.toFixed(2),
    bid: tick.bid?.toFixed(2),
    ask: tick.ask?.toFixed(2),
    spreadPips:
      tick.ask != null && tick.bid != null && pipSizeNum > 0
        ? ((tick.ask - tick.bid) / pipSizeNum).toFixed(1)
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
  showProgress = true,
  currentAtr,
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
  const [expanded, setExpanded] = useState(true);

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
          <Tooltip title={expanded ? 'Collapse header' : 'Expand header'}>
            <IconButton
              size="small"
              onClick={() => setExpanded((prev) => !prev)}
              aria-label={expanded ? 'Collapse header' : 'Expand header'}
            >
              {expanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}
            </IconButton>
          </Tooltip>
        </Box>

        <Collapse in={expanded}>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
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

            <Typography
              variant="body1"
              color="text.secondary"
              sx={{ pl: '4px', fontSize: { xs: '0.85rem', sm: '1rem' } }}
            >
              {strategyName}
            </Typography>

            {taskDescription && (
              <Typography
                variant="body2"
                color="text.secondary"
                sx={{ pl: '4px' }}
              >
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
                  sx={{ fontFamily: 'monospace', fontSize: 'inherit' }}
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
                  tickText.spreadPips && (
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
                        Spd {tickText.spreadPips} pips
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
                {currentAtr != null && (
                  <Typography
                    variant="caption"
                    color="text.secondary"
                    component="span"
                    sx={{ fontFamily: 'monospace', fontSize: 'inherit' }}
                  >
                    ATR {currentAtr.toFixed(5)}
                  </Typography>
                )}
              </Box>
            )}

            {showProgress &&
              (status === TaskStatus.RUNNING ||
                status === TaskStatus.STARTING) && (
                <Typography
                  variant="body2"
                  color="text.secondary"
                  sx={{ pl: '4px', fontWeight: 600 }}
                >
                  {Math.round(Math.min(Math.max(progress, 0), 100))}%{' '}
                  {completedLabel}
                </Typography>
              )}
          </Box>
        </Collapse>
      </Box>
    </Paper>
  );
}
