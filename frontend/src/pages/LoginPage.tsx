import { useState, type FormEvent } from 'react';
import { useNavigate, Link as RouterLink } from 'react-router-dom';
import {
  Container,
  Box,
  Typography,
  Paper,
  TextField,
  Button,
  Link,
  Alert,
  CircularProgress,
} from '@mui/material';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../contexts/AuthContext';
import { useLogin } from '../hooks/useAuthMutations';
import { ApiError } from '../api/apiClient';
import { logger } from '../utils/logger';

interface LoginFormData {
  email: string;
  password: string;
}

interface ErrorResponse {
  error?: string;
  detail?: string;
  message?: string;
  email?: string[];
  password?: string[];
}

const LoginPage = () => {
  const { t } = useTranslation('common');
  const navigate = useNavigate();
  const { login, systemSettings, systemSettingsLoading } = useAuth();
  const loginMutation = useLogin();

  const [formData, setFormData] = useState<LoginFormData>({
    email: '',
    password: '',
  });

  const [errors, setErrors] = useState<{
    email?: string;
    password?: string;
    general?: string;
  }>({});

  const [isLoading, setIsLoading] = useState(false);

  // Check if login is disabled
  const isLoginDisabled =
    !systemSettingsLoading && systemSettings && !systemSettings.login_enabled;

  const validateForm = (): boolean => {
    const newErrors: { email?: string; password?: string } = {};

    // Email validation
    if (!formData.email) {
      newErrors.email = t('validation.emailRequired');
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)) {
      newErrors.email = t('validation.invalidEmailFormat');
    }

    // Password validation
    if (!formData.password) {
      newErrors.password = t('validation.passwordRequired');
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    // Clear previous errors
    setErrors({});

    // Validate form
    if (!validateForm()) {
      return;
    }

    setIsLoading(true);

    try {
      const loginData = await loginMutation.mutate(formData);

      if (!loginData.token || !loginData.user) {
        setErrors({
          general: t('auth.loginFailedInvalidResponse'),
        });
        return;
      }

      login(loginData.token, loginData.user);

      // Redirect to default authenticated landing page
      navigate('/dashboard');
    } catch (error) {
      if (error instanceof ApiError) {
        const errorData = (error.body ?? {}) as ErrorResponse;
        const emailError = errorData.email?.[0];
        const passwordError = errorData.password?.[0];

        let general =
          errorData.error || errorData.detail || errorData.message || '';

        if (!general) {
          const statusText =
            `${error.status || ''} ${error.statusText || ''}`.trim();
          general = statusText
            ? t('auth.loginFailedWithStatus', { status: statusText })
            : t('auth.loginFailed');
        }

        // Prefer localized/friendlier messages for known login failures.
        // Keep backend-provided message when it contains specific details.
        if (error.status === 503) {
          general = t('auth.loginDisabled');
        } else if (error.status === 429) {
          general = general || t('auth.loginBlocked');
        } else if (error.status === 403) {
          const normalized = general.toLowerCase();
          if (
            normalized.includes('not authorized') ||
            normalized.includes('not whitelisted')
          ) {
            general = t('auth.emailNotWhitelisted');
          }
        }

        setErrors({
          general,
          email: emailError,
          password: passwordError,
        });
        return;
      }
      logger.error('Login error', {
        error: error instanceof Error ? error.message : String(error),
      });
      setErrors({
        general: t('errors.unexpectedError'),
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleChange =
    (field: keyof LoginFormData) =>
    (e: React.ChangeEvent<HTMLInputElement>) => {
      setFormData((prev) => ({
        ...prev,
        [field]: e.target.value,
      }));
      // Clear field error when user starts typing
      if (errors[field]) {
        setErrors((prev) => ({
          ...prev,
          [field]: undefined,
        }));
      }
    };

  return (
    <Container
      maxWidth={false}
      sx={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        minHeight: '100vh',
      }}
    >
      <Box
        sx={{
          width: '100%',
          maxWidth: '600px',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          px: 2,
        }}
      >
        <Box
          component="img"
          src="/logo.svg"
          alt="Logo"
          sx={{
            width: 120,
            height: 120,
            mb: 3,
          }}
        />
        <Paper elevation={3} sx={{ p: 4, width: '100%' }}>
          <Typography component="h1" variant="h5" align="center" gutterBottom>
            {t('auth.login')}
          </Typography>

          {systemSettingsLoading && (
            <Box sx={{ display: 'flex', justifyContent: 'center', mb: 2 }}>
              <CircularProgress size={24} />
            </Box>
          )}

          {isLoginDisabled && (
            <Alert severity="warning" sx={{ mb: 2 }}>
              {t('auth.loginDisabled')}
            </Alert>
          )}

          {errors.general && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {errors.general}
            </Alert>
          )}

          <Box component="form" onSubmit={handleSubmit} noValidate>
            <TextField
              margin="normal"
              required
              fullWidth
              id="email"
              label={t('auth.email')}
              name="email"
              autoComplete="email"
              autoFocus
              value={formData.email}
              onChange={handleChange('email')}
              error={!!errors.email}
              helperText={errors.email}
              disabled={isLoading}
            />

            <TextField
              margin="normal"
              required
              fullWidth
              name="password"
              label={t('auth.password')}
              type="password"
              id="password"
              autoComplete="current-password"
              value={formData.password}
              onChange={handleChange('password')}
              error={!!errors.password}
              helperText={errors.password}
              disabled={isLoading}
            />

            <Button
              type="submit"
              fullWidth
              variant="contained"
              sx={{ mt: 3, mb: 2 }}
              disabled={isLoading || isLoginDisabled || systemSettingsLoading}
            >
              {isLoading ? (
                <CircularProgress size={24} color="inherit" />
              ) : (
                t('auth.login')
              )}
            </Button>

            {!isLoginDisabled &&
              systemSettings?.registration_enabled &&
              !systemSettingsLoading && (
                <Box sx={{ textAlign: 'center' }}>
                  <Typography variant="body2" color="text.secondary">
                    {t('auth.noAccount')}{' '}
                    <Link
                      component={RouterLink}
                      to="/register"
                      underline="hover"
                    >
                      {t('auth.signUpHere')}
                    </Link>
                  </Typography>
                </Box>
              )}
          </Box>
        </Paper>
      </Box>
    </Container>
  );
};

export default LoginPage;
