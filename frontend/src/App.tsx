import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { CssBaseline, ThemeProvider } from '@mui/material';
import theme from './theme/theme';
import AppLayout from './components/layout/AppLayout';
import ProtectedRoute from './components/auth/ProtectedRoute';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import DashboardPage from './pages/DashboardPage';
import OrdersPage from './pages/OrdersPage';
import PositionsPage from './pages/PositionsPage';
import StrategyPage from './pages/StrategyPage';
import BacktestPage from './pages/BacktestPage';
import SettingsPage from './pages/SettingsPage';
import AdminDashboardPage from './pages/AdminDashboardPage';
import NotFoundPage from './pages/NotFoundPage';

function AppRoutes() {
  const { isAuthenticated, systemSettings, systemSettingsLoading } = useAuth();

  return (
    <Routes>
      {/* Public routes - conditionally rendered based on system settings */}
      {!systemSettingsLoading && systemSettings?.login_enabled && (
        <Route path="/login" element={<LoginPage />} />
      )}
      {!systemSettingsLoading && systemSettings?.registration_enabled && (
        <Route path="/register" element={<RegisterPage />} />
      )}

      {/* Redirect to login if routes are disabled */}
      {!systemSettingsLoading && !systemSettings?.login_enabled && (
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
      {!systemSettingsLoading && !systemSettings?.registration_enabled && (
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

      {/* Protected routes with layout */}
      <Route element={<ProtectedRoute isAuthenticated={isAuthenticated} />}>
        <Route element={<AppLayout />}>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/orders" element={<OrdersPage />} />
          <Route path="/positions" element={<PositionsPage />} />
          <Route path="/strategy" element={<StrategyPage />} />
          <Route path="/backtest" element={<BacktestPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/admin" element={<AdminDashboardPage />} />
        </Route>
      </Route>

      {/* 404 route */}
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}

function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <AuthProvider>
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
  );
}

export default App;
