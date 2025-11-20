import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import {
  CssBaseline,
  ThemeProvider,
  Box,
  CircularProgress,
} from '@mui/material';
import theme from './theme/theme';
import highContrastTheme from './theme/highContrastTheme';
import AppLayout from './components/layout/AppLayout';
import ProtectedRoute from './components/auth/ProtectedRoute';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { AccessibilityProvider } from './contexts/AccessibilityContext';
import { useAccessibility } from './hooks/useAccessibility';
import { ToastProvider } from './components/common';
import ErrorBoundary from './components/common/ErrorBoundary';
import { QueryProvider } from './providers/QueryProvider';

// Lazy load page components for code splitting
const LoginPage = lazy(() => import('./pages/LoginPage'));
const RegisterPage = lazy(() => import('./pages/RegisterPage'));
const DashboardPage = lazy(() => import('./pages/DashboardPage'));
const OrdersPage = lazy(() => import('./pages/OrdersPage'));
const PositionsPage = lazy(() => import('./pages/PositionsPage'));
const SettingsPage = lazy(() => import('./pages/SettingsPage'));
const ProfilePage = lazy(() => import('./pages/ProfilePage'));
const AdminDashboardPage = lazy(() => import('./pages/AdminDashboardPage'));
const AdminSystemSettingsPage = lazy(
  () => import('./pages/AdminSystemSettingsPage')
);
const AdminWhitelistPage = lazy(() => import('./pages/AdminWhitelistPage'));
const UserManagementPage = lazy(() => import('./pages/UserManagementPage'));
const NotFoundPage = lazy(() => import('./pages/NotFoundPage'));
const ConfigurationsPage = lazy(() => import('./pages/ConfigurationsPage'));
const ConfigurationFormPage = lazy(
  () => import('./pages/ConfigurationFormPage')
);
const BacktestTasksPage = lazy(() => import('./pages/BacktestTasksPage'));
const BacktestTaskFormPage = lazy(() => import('./pages/BacktestTaskFormPage'));
const BacktestTaskDetailPage = lazy(
  () => import('./pages/BacktestTaskDetailPage')
);
const TradingTasksPage = lazy(() => import('./pages/TradingTasksPage'));
const TradingTaskFormPage = lazy(() => import('./pages/TradingTaskFormPage'));
const TradingTaskDetailPage = lazy(
  () => import('./pages/TradingTaskDetailPage')
);
const CreateOrderPage = lazy(() => import('./pages/CreateOrderPage'));

// Loading fallback component
function PageLoadingFallback() {
  return (
    <Box
      sx={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        minHeight: '100vh',
      }}
    >
      <CircularProgress aria-label="Loading page" />
    </Box>
  );
}

function AppRoutes() {
  const { isAuthenticated, systemSettings, systemSettingsLoading } = useAuth();

  // Show loading state while fetching system settings
  if (systemSettingsLoading) {
    return (
      <Routes>
        <Route
          path="*"
          element={
            <Box
              sx={{
                display: 'flex',
                justifyContent: 'center',
                alignItems: 'center',
                minHeight: '100vh',
              }}
            >
              <CircularProgress />
            </Box>
          }
        />
      </Routes>
    );
  }

  return (
    <Suspense fallback={<PageLoadingFallback />}>
      <Routes>
        {/* Public routes - conditionally rendered based on system settings */}
        {systemSettings?.login_enabled && (
          <Route path="/login" element={<LoginPage />} />
        )}
        {systemSettings?.registration_enabled && (
          <Route path="/register" element={<RegisterPage />} />
        )}

        {/* Redirect to login if routes are disabled */}
        {!systemSettings?.login_enabled && (
          <Route
            path="/login"
            element={
              <Navigate
                to="/"
                replace
                state={{ message: 'Login is currently disabled' }}
              />
            }
          />
        )}
        {!systemSettings?.registration_enabled && (
          <Route
            path="/register"
            element={
              <Navigate
                to="/login"
                replace
                state={{ message: 'Registration is currently disabled' }}
              />
            }
          />
        )}

        {/* Root path - redirect to dashboard or login */}
        <Route
          path="/"
          element={
            isAuthenticated ? (
              <Navigate to="/dashboard" replace />
            ) : (
              <Navigate to="/login" replace />
            )
          }
        />

        {/* Protected routes with layout */}
        <Route element={<ProtectedRoute isAuthenticated={isAuthenticated} />}>
          <Route element={<AppLayout />}>
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/orders" element={<OrdersPage />} />
            <Route path="/orders/new" element={<CreateOrderPage />} />
            <Route path="/positions" element={<PositionsPage />} />
            <Route path="/profile" element={<ProfilePage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/configurations" element={<ConfigurationsPage />} />
            <Route
              path="/configurations/new"
              element={<ConfigurationFormPage />}
            />
            <Route
              path="/configurations/:id/edit"
              element={<ConfigurationFormPage />}
            />
            <Route path="/backtest-tasks" element={<BacktestTasksPage />} />
            <Route
              path="/backtest-tasks/new"
              element={<BacktestTaskFormPage />}
            />
            <Route
              path="/backtest-tasks/:id"
              element={<BacktestTaskDetailPage />}
            />
            <Route
              path="/backtest-tasks/:id/edit"
              element={<BacktestTaskFormPage />}
            />
            <Route path="/trading-tasks" element={<TradingTasksPage />} />
            <Route
              path="/trading-tasks/new"
              element={<TradingTaskFormPage />}
            />
            <Route
              path="/trading-tasks/:id"
              element={<TradingTaskDetailPage />}
            />
            <Route
              path="/trading-tasks/:id/edit"
              element={<TradingTaskFormPage />}
            />
            <Route path="/admin" element={<AdminDashboardPage />} />
            <Route
              path="/admin/settings"
              element={<AdminSystemSettingsPage />}
            />
            <Route path="/admin/whitelist" element={<AdminWhitelistPage />} />
            <Route path="/admin/users" element={<UserManagementPage />} />
          </Route>
        </Route>

        {/* 404 route */}
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </Suspense>
  );
}

function ThemedApp() {
  const { highContrastMode } = useAccessibility();
  const activeTheme = highContrastMode ? highContrastTheme : theme;

  return (
    <ThemeProvider theme={activeTheme}>
      <CssBaseline />
      <QueryProvider>
        <ToastProvider>
          <AuthProvider>
            <BrowserRouter>
              <AppRoutes />
            </BrowserRouter>
          </AuthProvider>
        </ToastProvider>
      </QueryProvider>
    </ThemeProvider>
  );
}

function App() {
  return (
    <ErrorBoundary level="app">
      <AccessibilityProvider>
        <ThemedApp />
      </AccessibilityProvider>
    </ErrorBoundary>
  );
}

export default App;
