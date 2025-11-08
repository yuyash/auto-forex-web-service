import React from 'react';
import { Box, Skeleton, Card, CardContent, Stack } from '@mui/material';

interface SkeletonLoaderProps {
  variant?: 'card' | 'list' | 'detail' | 'table';
  count?: number;
}

/**
 * Skeleton loader component for displaying loading states
 * Provides different variants for different UI patterns
 */
const SkeletonLoader: React.FC<SkeletonLoaderProps> = ({
  variant = 'card',
  count = 3,
}) => {
  if (variant === 'card') {
    return (
      <Stack spacing={2}>
        {Array.from({ length: count }).map((_, index) => (
          <Card key={index}>
            <CardContent>
              <Skeleton variant="text" width="60%" height={32} />
              <Skeleton variant="text" width="40%" height={24} sx={{ mt: 1 }} />
              <Box sx={{ mt: 2, display: 'flex', gap: 2 }}>
                <Skeleton variant="rectangular" width={100} height={36} />
                <Skeleton variant="rectangular" width={100} height={36} />
              </Box>
            </CardContent>
          </Card>
        ))}
      </Stack>
    );
  }

  if (variant === 'list') {
    return (
      <Stack spacing={1}>
        {Array.from({ length: count }).map((_, index) => (
          <Box
            key={index}
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 2,
              p: 2,
              border: '1px solid',
              borderColor: 'divider',
              borderRadius: 1,
            }}
          >
            <Skeleton variant="circular" width={40} height={40} />
            <Box sx={{ flex: 1 }}>
              <Skeleton variant="text" width="70%" height={24} />
              <Skeleton variant="text" width="50%" height={20} />
            </Box>
            <Skeleton variant="rectangular" width={80} height={32} />
          </Box>
        ))}
      </Stack>
    );
  }

  if (variant === 'detail') {
    return (
      <Box>
        <Skeleton variant="text" width="40%" height={40} sx={{ mb: 2 }} />
        <Skeleton variant="text" width="30%" height={24} sx={{ mb: 3 }} />
        <Box sx={{ display: 'flex', gap: 2, mb: 3 }}>
          {Array.from({ length: 4 }).map((_, index) => (
            <Card key={index} sx={{ flex: 1 }}>
              <CardContent>
                <Skeleton variant="text" width="60%" height={20} />
                <Skeleton
                  variant="text"
                  width="80%"
                  height={32}
                  sx={{ mt: 1 }}
                />
              </CardContent>
            </Card>
          ))}
        </Box>
        <Skeleton variant="rectangular" width="100%" height={300} />
      </Box>
    );
  }

  if (variant === 'table') {
    return (
      <Box>
        <Box sx={{ display: 'flex', gap: 2, mb: 2, p: 2, bgcolor: 'grey.100' }}>
          <Skeleton variant="text" width="20%" height={24} />
          <Skeleton variant="text" width="20%" height={24} />
          <Skeleton variant="text" width="20%" height={24} />
          <Skeleton variant="text" width="20%" height={24} />
          <Skeleton variant="text" width="20%" height={24} />
        </Box>
        {Array.from({ length: count }).map((_, index) => (
          <Box
            key={index}
            sx={{
              display: 'flex',
              gap: 2,
              p: 2,
              borderBottom: '1px solid',
              borderColor: 'divider',
            }}
          >
            <Skeleton variant="text" width="20%" height={20} />
            <Skeleton variant="text" width="20%" height={20} />
            <Skeleton variant="text" width="20%" height={20} />
            <Skeleton variant="text" width="20%" height={20} />
            <Skeleton variant="text" width="20%" height={20} />
          </Box>
        ))}
      </Box>
    );
  }

  return null;
};

export default SkeletonLoader;
