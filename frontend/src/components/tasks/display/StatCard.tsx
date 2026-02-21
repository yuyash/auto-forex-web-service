import React from 'react';
import { Card, CardContent, Typography, Box, Skeleton } from '@mui/material';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import TrendingDownIcon from '@mui/icons-material/TrendingDown';

interface StatCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon?: React.ReactNode;
  trend?: 'up' | 'down' | 'neutral';
  trendValue?: string;
  isLoading?: boolean;
  color?: 'primary' | 'success' | 'error' | 'warning' | 'info' | 'default';
  onClick?: () => void;
}

export const StatCard: React.FC<StatCardProps> = React.memo(
  ({
    title,
    value,
    subtitle,
    icon,
    trend,
    trendValue,
    isLoading = false,
    color = 'default',
    onClick,
  }) => {
    const getTrendColor = React.useMemo(() => {
      if (trend === 'up') return 'success.main';
      if (trend === 'down') return 'error.main';
      return 'text.secondary';
    }, [trend]);

    const getTrendIcon = React.useMemo(() => {
      if (trend === 'up') return <TrendingUpIcon fontSize="small" />;
      if (trend === 'down') return <TrendingDownIcon fontSize="small" />;
      return null;
    }, [trend]);

    const getColorStyles = React.useMemo(() => {
      const colorMap = {
        primary: { bgcolor: 'primary.light', color: 'primary.main' },
        success: { bgcolor: 'success.light', color: 'success.main' },
        error: { bgcolor: 'error.light', color: 'error.main' },
        warning: { bgcolor: 'warning.light', color: 'warning.main' },
        info: { bgcolor: 'info.light', color: 'info.main' },
        default: { bgcolor: 'action.hover', color: 'text.primary' },
      };
      return colorMap[color];
    }, [color]);

    const handleKeyDown = React.useCallback(
      (e: React.KeyboardEvent) => {
        if (onClick && (e.key === 'Enter' || e.key === ' ')) {
          e.preventDefault();
          onClick();
        }
      },
      [onClick]
    );

    return (
      <Card
        role="article"
        aria-label={`${title}: ${value}`}
        tabIndex={onClick ? 0 : undefined}
        onKeyDown={onClick ? handleKeyDown : undefined}
        sx={{
          height: '100%',
          cursor: onClick ? 'pointer' : 'default',
          transition: 'all 0.2s',
          '&:hover': onClick
            ? {
                transform: 'translateY(-4px)',
                boxShadow: 3,
              }
            : {},
          '&:focus-visible': onClick
            ? {
                outline: '2px solid',
                outlineColor: 'primary.main',
                outlineOffset: '2px',
              }
            : {},
        }}
        onClick={onClick}
      >
        <CardContent>
          <Box
            sx={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'flex-start',
              mb: 2,
            }}
          >
            <Typography
              variant="body2"
              color="text.secondary"
              sx={{ fontWeight: 500 }}
            >
              {title}
            </Typography>
            {icon && (
              <Box
                sx={{
                  ...getColorStyles,
                  borderRadius: 1,
                  p: 0.5,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                {icon}
              </Box>
            )}
          </Box>

          {isLoading ? (
            <>
              <Skeleton variant="text" width="60%" height={40} />
              {subtitle && <Skeleton variant="text" width="40%" />}
            </>
          ) : (
            <>
              <Typography
                variant="h4"
                component="div"
                sx={{ fontWeight: 600, mb: 0.5 }}
              >
                {value}
              </Typography>

              {(subtitle || trendValue) && (
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  {subtitle && (
                    <Typography variant="body2" color="text.secondary">
                      {subtitle}
                    </Typography>
                  )}
                  {trendValue && (
                    <Box
                      sx={{
                        display: 'flex',
                        alignItems: 'center',
                        color: getTrendColor,
                      }}
                    >
                      {getTrendIcon}
                      <Typography
                        variant="body2"
                        sx={{ ml: 0.5, fontWeight: 500 }}
                      >
                        {trendValue}
                      </Typography>
                    </Box>
                  )}
                </Box>
              )}
            </>
          )}
        </CardContent>
      </Card>
    );
  }
);
