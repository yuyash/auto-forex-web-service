import React from 'react';

type ViewMode = 'all' | 'byDirection' | 'byStatus';

interface TaskPositionModeViewsProps {
  viewMode: ViewMode;
  all: React.ReactNode;
  byDirection: React.ReactNode;
  byStatus: React.ReactNode;
}

export const TaskPositionModeViews: React.FC<TaskPositionModeViewsProps> = ({
  viewMode,
  all,
  byDirection,
  byStatus,
}) => {
  if (viewMode === 'all') {
    return <>{all}</>;
  }
  if (viewMode === 'byDirection') {
    return <>{byDirection}</>;
  }
  return <>{byStatus}</>;
};
