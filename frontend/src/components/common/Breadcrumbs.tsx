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
      { label: t('breadcrumbs.configurations') },
    ],
    '/configurations/new': [
      { label: t('breadcrumbs.home'), path: homePath },
      { label: t('breadcrumbs.configurations'), path: '/configurations' },
      { label: t('breadcrumbs.newConfiguration') },
    ],
    '/configurations/compare': [
      { label: t('breadcrumbs.home'), path: homePath },
      { label: t('breadcrumbs.configurations'), path: '/configurations' },
      { label: t('breadcrumbs.compare') },
    ],
    // Backtest Task routes
    '/backtest-tasks': [
      { label: t('breadcrumbs.home'), path: homePath },
      { label: t('breadcrumbs.backtestTasks') },
    ],
    '/backtest-tasks/new': [
      { label: t('breadcrumbs.home'), path: homePath },
      { label: t('breadcrumbs.backtestTasks'), path: '/backtest-tasks' },
      { label: t('breadcrumbs.newTask') },
    ],
    '/backtest-tasks/compare': [
      { label: t('breadcrumbs.home'), path: homePath },
      { label: t('breadcrumbs.backtestTasks'), path: '/backtest-tasks' },
      { label: t('breadcrumbs.compare') },
    ],
    // Trading Task routes
    '/trading-tasks': [
      { label: t('breadcrumbs.home'), path: homePath },
      { label: t('breadcrumbs.tradingTasks') },
    ],
    '/trading-tasks/new': [
      { label: t('breadcrumbs.home'), path: homePath },
      { label: t('breadcrumbs.tradingTasks'), path: '/trading-tasks' },
      { label: t('breadcrumbs.newTask') },
    ],
    '/trading-tasks/compare': [
      { label: t('breadcrumbs.home'), path: homePath },
      { label: t('breadcrumbs.tradingTasks'), path: '/trading-tasks' },
      { label: t('breadcrumbs.compare') },
    ],
    // Settings routes
    '/settings': [
      { label: t('breadcrumbs.home'), path: homePath },
      { label: t('breadcrumbs.settings') },
    ],
    // OANDA Accounts routes
    '/oanda-accounts': [
      { label: t('breadcrumbs.home'), path: homePath },
      { label: t('breadcrumbs.oandaAccounts') },
    ],
  };

  // If customPath is provided, use it directly
  if (customPath) {
    const breadcrumbs = [
      { label: t('breadcrumbs.home'), path: homePath },
      ...customPath,
      {
        label: location.pathname.includes('/edit')
          ? t('breadcrumbs.editConfiguration')
          : t('breadcrumbs.configuration'),
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
        { label: t('breadcrumbs.backtestTasks'), path: '/backtest-tasks' },
        { label: t('breadcrumbs.configurations') },
      ];
    } else if (fromPage === 'trading-tasks') {
      breadcrumbs = [
        { label: t('breadcrumbs.home'), path: homePath },
        { label: t('breadcrumbs.tradingTasks'), path: '/trading-tasks' },
        { label: t('breadcrumbs.configurations') },
      ];
    }
  }

  // Special handling for new configuration page with context
  if (location.pathname === '/configurations/new' && fromPage) {
    if (fromPage === 'backtest-tasks') {
      breadcrumbs = [
        { label: t('breadcrumbs.home'), path: homePath },
        { label: t('breadcrumbs.backtestTasks'), path: '/backtest-tasks' },
        {
          label: t('breadcrumbs.configurations'),
          path: '/configurations?from=backtest-tasks',
        },
        { label: t('breadcrumbs.newConfiguration') },
      ];
    } else if (fromPage === 'trading-tasks') {
      breadcrumbs = [
        { label: t('breadcrumbs.home'), path: homePath },
        { label: t('breadcrumbs.tradingTasks'), path: '/trading-tasks' },
        {
          label: t('breadcrumbs.configurations'),
          path: '/configurations?from=trading-tasks',
        },
        { label: t('breadcrumbs.newConfiguration') },
      ];
    }
  }

  if (!breadcrumbs) {
    // Check for dynamic routes
    if (location.pathname.match(/^\/configurations\/\d+\/edit$/)) {
      if (fromPage === 'backtest-tasks') {
        breadcrumbs = [
          { label: t('breadcrumbs.home'), path: homePath },
          { label: t('breadcrumbs.backtestTasks'), path: '/backtest-tasks' },
          {
            label: t('breadcrumbs.configurations'),
            path: '/configurations?from=backtest-tasks',
          },
          { label: t('breadcrumbs.editConfiguration') },
        ];
      } else if (fromPage === 'trading-tasks') {
        breadcrumbs = [
          { label: t('breadcrumbs.home'), path: homePath },
          { label: t('breadcrumbs.tradingTasks'), path: '/trading-tasks' },
          {
            label: t('breadcrumbs.configurations'),
            path: '/configurations?from=trading-tasks',
          },
          { label: t('breadcrumbs.editConfiguration') },
        ];
      } else {
        breadcrumbs = [
          { label: t('breadcrumbs.home'), path: homePath },
          { label: t('breadcrumbs.configurations'), path: '/configurations' },
          { label: t('breadcrumbs.editConfiguration') },
        ];
      }
    } else if (location.pathname.match(/^\/configurations\/\d+$/)) {
      breadcrumbs = [
        { label: t('breadcrumbs.home'), path: homePath },
        { label: t('breadcrumbs.configurations'), path: '/configurations' },
        { label: t('breadcrumbs.configurationDetails') },
      ];
    } else if (location.pathname.match(/^\/backtest-tasks\/[^/]+$/)) {
      breadcrumbs = [
        { label: t('breadcrumbs.home'), path: homePath },
        { label: t('breadcrumbs.backtestTasks'), path: '/backtest-tasks' },
        { label: t('breadcrumbs.taskDetails') },
      ];
    } else if (location.pathname.match(/^\/backtest-tasks\/[^/]+\/edit$/)) {
      breadcrumbs = [
        { label: t('breadcrumbs.home'), path: homePath },
        { label: t('breadcrumbs.backtestTasks'), path: '/backtest-tasks' },
        { label: t('breadcrumbs.editTask') },
      ];
    } else if (location.pathname.match(/^\/trading-tasks\/[^/]+$/)) {
      breadcrumbs = [
        { label: t('breadcrumbs.home'), path: homePath },
        { label: t('breadcrumbs.tradingTasks'), path: '/trading-tasks' },
        { label: t('breadcrumbs.taskDetails') },
      ];
    } else if (location.pathname.match(/^\/trading-tasks\/[^/]+\/edit$/)) {
      breadcrumbs = [
        { label: t('breadcrumbs.home'), path: homePath },
        { label: t('breadcrumbs.tradingTasks'), path: '/trading-tasks' },
        { label: t('breadcrumbs.editTask') },
      ];
    } else if (location.pathname.match(/^\/oanda-accounts\/\d+$/)) {
      breadcrumbs = [
        { label: t('breadcrumbs.home'), path: homePath },
        {
          label: t('breadcrumbs.oandaAccounts'),
          path: '/oanda-accounts',
        },
        { label: t('breadcrumbs.accountDetails') },
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
