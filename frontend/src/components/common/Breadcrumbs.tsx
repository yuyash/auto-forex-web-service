import { Breadcrumbs as MuiBreadcrumbs, Link, Typography } from '@mui/material';
import {
  Link as RouterLink,
  useLocation,
  useSearchParams,
} from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import NavigateNextIcon from '@mui/icons-material/NavigateNext';
import HomeIcon from '@mui/icons-material/Home';

interface BreadcrumbItem {
  label: string;
  path?: string;
}

interface BreadcrumbsProps {
  customPath?: BreadcrumbItem[];
}

const Breadcrumbs = ({ customPath }: BreadcrumbsProps = {}) => {
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const { t } = useTranslation('common');

  const homePath = '/dashboard';

  // Check if we came from a specific page (via query param)
  const fromPage = searchParams.get('from');

  // Route configuration for breadcrumbs
  const routeConfig: Record<string, BreadcrumbItem[]> = {
    // Configuration routes - default without context
    '/configurations': [
      { label: t('breadcrumbs.home'), path: homePath },
      { label: 'Configurations' },
    ],
    '/configurations/new': [
      { label: t('breadcrumbs.home'), path: homePath },
      { label: 'Configurations', path: '/configurations' },
      { label: 'New Configuration' },
    ],
    // Backtest Task routes
    '/backtest-tasks': [
      { label: t('breadcrumbs.home'), path: homePath },
      { label: 'Backtest Tasks' },
    ],
    '/backtest-tasks/new': [
      { label: t('breadcrumbs.home'), path: homePath },
      { label: 'Backtest Tasks', path: '/backtest-tasks' },
      { label: 'New Task' },
    ],
    // Trading Task routes
    '/trading-tasks': [
      { label: t('breadcrumbs.home'), path: homePath },
      { label: 'Trading Tasks' },
    ],
    '/trading-tasks/new': [
      { label: t('breadcrumbs.home'), path: homePath },
      { label: 'Trading Tasks', path: '/trading-tasks' },
      { label: 'New Task' },
    ],
    // Settings routes
    '/settings': [
      { label: t('breadcrumbs.home'), path: homePath },
      { label: 'Settings' },
    ],
  };

  // If customPath is provided, use it directly
  if (customPath) {
    const breadcrumbs = [
      { label: t('breadcrumbs.home'), path: homePath },
      ...customPath,
      {
        label: location.pathname.includes('/edit')
          ? 'Edit Configuration'
          : 'Configuration',
      },
    ];

    return (
      <MuiBreadcrumbs
        separator={<NavigateNextIcon fontSize="small" />}
        aria-label="breadcrumb"
        sx={{ mb: 1 }}
      >
        {breadcrumbs.map((crumb, index) => {
          const isLast = index === breadcrumbs.length - 1;

          if (isLast) {
            return (
              <Typography
                key={crumb.label}
                color="text.primary"
                sx={{ display: 'flex', alignItems: 'center' }}
              >
                {index === 0 && (
                  <HomeIcon sx={{ mr: 0.5 }} fontSize="inherit" />
                )}
                {crumb.label}
              </Typography>
            );
          }

          return (
            <Link
              key={crumb.label}
              component={RouterLink}
              to={crumb.path || '#'}
              underline="hover"
              color="inherit"
              sx={{ display: 'flex', alignItems: 'center' }}
            >
              {index === 0 && <HomeIcon sx={{ mr: 0.5 }} fontSize="inherit" />}
              {crumb.label}
            </Link>
          );
        })}
      </MuiBreadcrumbs>
    );
  }

  // Handle dynamic routes (e.g., /backtest-tasks/:id, /configurations/:id/edit)
  let breadcrumbs = routeConfig[location.pathname];

  // Special handling for configurations page with context
  if (location.pathname === '/configurations' && fromPage) {
    if (fromPage === 'backtest-tasks') {
      breadcrumbs = [
        { label: t('breadcrumbs.home'), path: homePath },
        { label: 'Backtest Tasks', path: '/backtest-tasks' },
        { label: 'Configurations' },
      ];
    } else if (fromPage === 'trading-tasks') {
      breadcrumbs = [
        { label: t('breadcrumbs.home'), path: homePath },
        { label: 'Trading Tasks', path: '/trading-tasks' },
        { label: 'Configurations' },
      ];
    }
  }

  // Special handling for new configuration page with context
  if (location.pathname === '/configurations/new' && fromPage) {
    if (fromPage === 'backtest-tasks') {
      breadcrumbs = [
        { label: t('breadcrumbs.home'), path: homePath },
        { label: 'Backtest Tasks', path: '/backtest-tasks' },
        {
          label: 'Configurations',
          path: '/configurations?from=backtest-tasks',
        },
        { label: 'New Configuration' },
      ];
    } else if (fromPage === 'trading-tasks') {
      breadcrumbs = [
        { label: t('breadcrumbs.home'), path: homePath },
        { label: 'Trading Tasks', path: '/trading-tasks' },
        { label: 'Configurations', path: '/configurations?from=trading-tasks' },
        { label: 'New Configuration' },
      ];
    }
  }

  if (!breadcrumbs) {
    // Check for dynamic routes
    if (location.pathname.match(/^\/configurations\/\d+\/edit$/)) {
      if (fromPage === 'backtest-tasks') {
        breadcrumbs = [
          { label: t('breadcrumbs.home'), path: homePath },
          { label: 'Backtest Tasks', path: '/backtest-tasks' },
          {
            label: 'Configurations',
            path: '/configurations?from=backtest-tasks',
          },
          { label: 'Edit Configuration' },
        ];
      } else if (fromPage === 'trading-tasks') {
        breadcrumbs = [
          { label: t('breadcrumbs.home'), path: homePath },
          { label: 'Trading Tasks', path: '/trading-tasks' },
          {
            label: 'Configurations',
            path: '/configurations?from=trading-tasks',
          },
          { label: 'Edit Configuration' },
        ];
      } else {
        breadcrumbs = [
          { label: t('breadcrumbs.home'), path: homePath },
          { label: 'Configurations', path: '/configurations' },
          { label: 'Edit Configuration' },
        ];
      }
    } else if (location.pathname.match(/^\/backtest-tasks\/\d+$/)) {
      breadcrumbs = [
        { label: t('breadcrumbs.home'), path: homePath },
        { label: 'Backtest Tasks', path: '/backtest-tasks' },
        { label: 'Task Details' },
      ];
    } else if (location.pathname.match(/^\/backtest-tasks\/\d+\/edit$/)) {
      breadcrumbs = [
        { label: t('breadcrumbs.home'), path: homePath },
        { label: 'Backtest Tasks', path: '/backtest-tasks' },
        { label: 'Edit Task' },
      ];
    } else if (location.pathname.match(/^\/trading-tasks\/\d+$/)) {
      breadcrumbs = [
        { label: t('breadcrumbs.home'), path: homePath },
        { label: 'Trading Tasks', path: '/trading-tasks' },
        { label: 'Task Details' },
      ];
    } else if (location.pathname.match(/^\/trading-tasks\/\d+\/edit$/)) {
      breadcrumbs = [
        { label: t('breadcrumbs.home'), path: homePath },
        { label: 'Trading Tasks', path: '/trading-tasks' },
        { label: 'Edit Task' },
      ];
    } else {
      // Default fallback
      breadcrumbs = [{ label: t('breadcrumbs.home'), path: homePath }];
    }
  }

  return (
    <MuiBreadcrumbs
      separator={<NavigateNextIcon fontSize="small" />}
      aria-label="breadcrumb"
      sx={{ mb: 1 }}
    >
      {breadcrumbs.map((crumb, index) => {
        const isLast = index === breadcrumbs.length - 1;

        if (isLast) {
          return (
            <Typography
              key={crumb.label}
              color="text.primary"
              sx={{ display: 'flex', alignItems: 'center' }}
            >
              {index === 0 && <HomeIcon sx={{ mr: 0.5 }} fontSize="inherit" />}
              {crumb.label}
            </Typography>
          );
        }

        return (
          <Link
            key={crumb.label}
            component={RouterLink}
            to={crumb.path || '#'}
            underline="hover"
            color="inherit"
            sx={{ display: 'flex', alignItems: 'center' }}
          >
            {index === 0 && <HomeIcon sx={{ mr: 0.5 }} fontSize="inherit" />}
            {crumb.label}
          </Link>
        );
      })}
    </MuiBreadcrumbs>
  );
};

export default Breadcrumbs;
