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
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import DashboardPage from './pages/DashboardPage';
import OrdersPage from './pages/OrdersPage';
import PositionsPage from './pages/PositionsPage';
import StrategyPage from './pages/StrategyPage';
import BacktestPage from './pages/BacktestPage';
import SettingsPage from './pages/SettingsPage';
import ProfilePage from './pages/ProfilePage';
import AdminDashboardPage from './pages/AdminDashboardPage';
import AdminSettingsPage from './pages/AdminSettingsPage';
import EventViewerPage from './pages/EventViewerPage';
import UserManagementPage from './pages/UserManagementPage';
import NotFoundPage from './pages/NotFoundPage';
import ConfigurationsPage from './pages/ConfigurationsPage';
import ConfigurationFormPage from './pages/ConfigurationFormPage';
import BacktestTasksPage from './pages/BacktestTasksPage';
import BacktestTaskFormPage from './pages/BacktestTaskFormPage';
import BacktestTaskDetailPage from './pages/BacktestTaskDetailPage';
import TradingTasksPage from './pages/TradingTasksPage';
import TradingTaskFormPage from './pages/TradingTaskFormPage';
import TradingTaskDetailPage from './pages/TradingTaskDetailPage';

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
          <Route path="/positions" element={<PositionsPage />} />
          <Route path="/strategy" element={<StrategyPage />} />
          <Route path="/backtest" element={<BacktestPage />} />
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
          <Route path="/trading-tasks/new" element={<TradingTaskFormPage />} />
          <Route
            path="/trading-tasks/:id"
            element={<TradingTaskDetailPage />}
          />
          <Route
            path="/trading-tasks/:id/edit"
            element={<TradingTaskFormPage />}
          />
          <Route path="/admin" element={<AdminDashboardPage />} />
          <Route path="/admin/settings" element={<AdminSettingsPage />} />
          <Route path="/admin/events" element={<EventViewerPage />} />
          <Route path="/admin/users" element={<UserManagementPage />} />
        </Route>
      </Route>

      {/* 404 route */}
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}

function ThemedApp() {
  const { highContrastMode } = useAccessibility();
  const activeTheme = highContrastMode ? highContrastTheme : theme;

  return (
    <ThemeProvider theme={activeTheme}>
      <CssBaseline />
      <ToastProvider>
        <AuthProvider>
          <BrowserRouter>
            <AppRoutes />
          </BrowserRouter>
        </AuthProvider>
      </ToastProvider>
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
