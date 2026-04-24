import { Settings as SettingsIcon } from '@mui/icons-material';
import { Box, IconButton, Tab, Tabs, Tooltip } from '@mui/material';
import type { SyntheticEvent } from 'react';
import type { TabItem } from '../../../hooks/useTabConfig';
import { componentDensity } from '../../../theme/density';

function a11yProps(index: number) {
  return {
    id: `task-tab-${index}`,
    'aria-controls': `task-tabpanel-${index}`,
  };
}

interface TaskDetailTabsProps {
  activeTabIndex: number;
  visibleTabs: TabItem[];
  onTabChange: (_event: SyntheticEvent, newValue: number) => void;
  onConfigureTabs: () => void;
  configureTabsLabel: string;
}

export function TaskDetailTabs({
  activeTabIndex,
  visibleTabs,
  onTabChange,
  onConfigureTabs,
  configureTabsLabel,
}: TaskDetailTabsProps) {
  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        borderBottom: 1,
        borderColor: 'divider',
        flexShrink: 0,
      }}
    >
      <Tabs
        value={activeTabIndex}
        onChange={onTabChange}
        aria-label="task detail tabs"
        variant="scrollable"
        scrollButtons="auto"
        allowScrollButtonsMobile
        sx={{
          flex: 1,
          minHeight: 40,
          '& .MuiTabs-scrollButtons': {
            width: 32,
          },
        }}
      >
        {visibleTabs.map((tab, idx) => (
          <Tab
            key={tab.id}
            label={tab.label}
            {...a11yProps(idx)}
            sx={{
              minWidth: { xs: 'auto', sm: 90 },
              minHeight: 40,
              px: { xs: 1, sm: 1.5 },
              fontSize: componentDensity.controlFontSize,
            }}
          />
        ))}
      </Tabs>
      <Tooltip title={configureTabsLabel}>
        <IconButton
          onClick={onConfigureTabs}
          size="small"
          sx={{ mr: 1 }}
          aria-label={configureTabsLabel}
        >
          <SettingsIcon fontSize="small" />
        </IconButton>
      </Tooltip>
    </Box>
  );
}
