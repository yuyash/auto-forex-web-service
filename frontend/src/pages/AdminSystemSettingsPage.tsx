import { useState, useEffect } from 'react';
import {
  Container,
  Typography,
  Box,
  Paper,
  TextField,
  Button,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  FormControlLabel,
  Switch,
  Alert,
  CircularProgress,
  Divider,
  Grid,
  InputAdornment,
  IconButton,
  LinearProgress,
} from '@mui/material';
import {
  Save as SaveIcon,
  Refresh as RefreshIcon,
  Visibility,
  VisibilityOff,
  Email as EmailIcon,
} from '@mui/icons-material';
import { useAuth } from '../contexts/AuthContext';
import { Breadcrumbs } from '../components/common';
import { useToast } from '../components/common/useToast';

interface SystemSettings {
  registration_enabled: boolean;
  login_enabled: boolean;
  email_whitelist_enabled: boolean;
  debug_mode: boolean;
  email_backend_type: string;
  email_host: string;
  email_port: number;
  email_use_tls: boolean;
  email_use_ssl: boolean;
  email_host_user: string;
  email_host_password: string;
  default_from_email: string;
  aws_credential_method: string;
  aws_profile_name: string;
  aws_role_arn: string;
  aws_credentials_file_path: string;
  aws_access_key_id: string;
  aws_secret_access_key: string;
  aws_ses_region: string;
  aws_region: string;
  athena_database_name: string;
  athena_table_name: string;
  athena_output_bucket: string;
  athena_instruments: string;
  athena_query_timeout: number;
  django_log_level: string;
  backtest_cpu_limit: number;
  backtest_memory_limit: number;
  tick_data_retention_days: number;
  tick_data_instruments: string;
  system_health_update_interval: number;
  external_api_check_interval: number;
  oanda_sync_interval_seconds: number;
  oanda_fetch_duration_days: number;
  updated_at: string;
}

const AdminSystemSettingsPage = () => {
  const { token } = useAuth();
  const { showSuccess, showError } = useToast();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [settings, setSettings] = useState<SystemSettings | null>(null);
  const [showEmailPassword, setShowEmailPassword] = useState(false);
  const [showAwsSecret, setShowAwsSecret] = useState(false);
  const [testingEmail, setTestingEmail] = useState(false);
  const [testEmailAddress, setTestEmailAddress] = useState('');
  const [testingAws, setTestingAws] = useState(false);
  const [triggeringImport, setTriggeringImport] = useState(false);
  const [importStartDate, setImportStartDate] = useState('');
  const [importEndDate, setImportEndDate] = useState('');
  const [importInProgress, setImportInProgress] = useState(false);
  const [importProgress, setImportProgress] = useState<{
    current_day: number;
    total_days: number;
    percentage: number;
    status: string;
    message: string;
    error?: string;
  } | null>(null);
  const [importCompleted, setImportCompleted] = useState(false);
  const [importFailed, setImportFailed] = useState(false);

  const fetchSettings = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/admin/system/settings', {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error('Failed to fetch settings');
      }

      const data = await response.json();
      setSettings(data);
    } catch (error) {
      showError('Failed to load system settings');
      console.error('Error fetching settings:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSettings();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  // Polling mechanism for import progress
  useEffect(() => {
    if (!importInProgress) return;

    const pollInterval = setInterval(async () => {
      try {
        const response = await fetch('/api/admin/athena-import-progress', {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        if (response.ok) {
          const data = await response.json();
          setImportProgress({
            current_day: data.current_day,
            total_days: data.total_days,
            percentage: data.percentage,
            status: data.status,
            message: data.message,
            error: data.error,
          });

          // Stop polling if complete or failed
          if (data.status === 'completed') {
            setImportInProgress(false);
            setImportCompleted(true);
            setImportFailed(false);
            clearInterval(pollInterval);
          } else if (data.status === 'failed') {
            setImportInProgress(false);
            setImportCompleted(false);
            setImportFailed(true);
            clearInterval(pollInterval);
          }
        } else if (response.status === 404) {
          // No import in progress
          setImportInProgress(false);
          setImportProgress(null);
          clearInterval(pollInterval);
        }
      } catch (error) {
        // Handle polling errors gracefully - log to console and continue polling
        console.error('Failed to fetch import progress:', error);
      }
    }, 2000); // Poll every 2 seconds

    // Clean up interval on component unmount
    return () => clearInterval(pollInterval);
  }, [importInProgress, token]);

  const handleSave = async () => {
    if (!settings) return;

    try {
      setSaving(true);
      const response = await fetch('/api/admin/system/settings', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(settings),
      });

      if (!response.ok) {
        throw new Error('Failed to save settings');
      }

      showSuccess('System settings saved successfully');
      fetchSettings(); // Reload to get updated timestamp
    } catch (error) {
      showError('Failed to save system settings');
      console.error('Error saving settings:', error);
    } finally {
      setSaving(false);
    }
  };

  const handleChange = (
    field: keyof SystemSettings,
    value: string | number | boolean
  ) => {
    if (!settings) return;
    setSettings({ ...settings, [field]: value });
  };

  const handleTestEmail = async () => {
    if (!testEmailAddress) {
      showError('Please enter an email address');
      return;
    }

    try {
      setTestingEmail(true);
      const response = await fetch('/api/admin/test-email', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ test_email: testEmailAddress }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || 'Failed to send test email');
      }

      showSuccess(`Test email sent successfully to ${testEmailAddress}`);
      setTestEmailAddress('');
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : 'Failed to send test email';
      showError(errorMessage);
      console.error('Error sending test email:', error);
    } finally {
      setTestingEmail(false);
    }
  };

  const handleTestAws = async () => {
    try {
      setTestingAws(true);
      const response = await fetch('/api/admin/test-aws', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || 'Failed to test AWS configuration');
      }

      const identity = data.configuration.caller_identity;
      const identityInfo = identity
        ? ` | Account: ${identity.account} | ARN: ${identity.arn}`
        : '';

      showSuccess(
        `AWS S3 connection successful! Bucket: ${data.configuration.bucket}${identityInfo}`
      );
    } catch (error) {
      const errorMessage =
        error instanceof Error
          ? error.message
          : 'Failed to test AWS configuration';
      showError(errorMessage);
      console.error('Error testing AWS:', error);
    } finally {
      setTestingAws(false);
    }
  };

  const handleTriggerAthenaImport = async () => {
    try {
      setTriggeringImport(true);
      setImportProgress(null);
      setImportCompleted(false);
      setImportFailed(false);

      const body: { start_date?: string; end_date?: string } = {};
      if (importStartDate && importEndDate) {
        body.start_date = new Date(importStartDate).toISOString();
        body.end_date = new Date(importEndDate).toISOString();
      }

      const response = await fetch('/api/admin/trigger-athena-import', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(body),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || 'Failed to trigger Athena import');
      }

      const totalDays = data.total_days || 1;

      // Initialize progress state with data from trigger response
      setImportProgress({
        current_day: 0,
        total_days: totalDays,
        percentage: 0,
        status: 'running',
        message: `Starting import for ${totalDays} day(s)...`,
      });

      // Start polling for progress updates
      setImportInProgress(true);

      showSuccess(
        `Athena import started for ${totalDays} day(s)! ${data.task_ids?.length || 1} task(s) queued.`
      );
    } catch (error) {
      const errorMessage =
        error instanceof Error
          ? error.message
          : 'Failed to trigger Athena import';
      showError(errorMessage);
      console.error('Error triggering Athena import:', error);
      setImportProgress(null);
      setImportInProgress(false);
    } finally {
      setTriggeringImport(false);
    }
  };

  const handleRetryImport = () => {
    // Clear error state and retry
    setImportFailed(false);
    setImportCompleted(false);
    setImportProgress(null);
    handleTriggerAthenaImport();
  };

  const handleClearImportStatus = () => {
    // Clear completion/error state
    setImportCompleted(false);
    setImportFailed(false);
    setImportProgress(null);
  };

  if (loading) {
    return (
      <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
          <CircularProgress />
        </Box>
      </Container>
    );
  }

  if (!settings) {
    return (
      <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
        <Alert severity="error">Failed to load system settings</Alert>
      </Container>
    );
  }

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
      <Breadcrumbs />

      <Box sx={{ mb: 4 }}>
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            mb: 2,
          }}
        >
          <Typography variant="h4">System Settings</Typography>
          <Box sx={{ display: 'flex', gap: 2 }}>
            <Button
              variant="outlined"
              startIcon={<RefreshIcon />}
              onClick={fetchSettings}
              disabled={saving}
            >
              Refresh
            </Button>
            <Button
              variant="contained"
              startIcon={<SaveIcon />}
              onClick={handleSave}
              disabled={saving}
            >
              {saving ? 'Saving...' : 'Save Changes'}
            </Button>
          </Box>
        </Box>
        <Typography variant="body2" color="text.secondary">
          Last updated: {new Date(settings.updated_at).toLocaleString()}
        </Typography>
      </Box>

      <Alert severity="warning" sx={{ mb: 3 }}>
        Changing Debug Mode or Log Level will automatically restart the backend
        container to apply changes. Other settings take effect immediately.
      </Alert>

      {/* General Settings */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" gutterBottom>
          General Settings
        </Typography>
        <Divider sx={{ mb: 3 }} />
        <Grid container spacing={3}>
          <Grid size={{ xs: 12, md: 6 }}>
            <FormControlLabel
              control={
                <Switch
                  checked={settings.registration_enabled}
                  onChange={(e) =>
                    handleChange('registration_enabled', e.target.checked)
                  }
                />
              }
              label="Enable User Registration"
            />
          </Grid>
          <Grid size={{ xs: 12, md: 6 }}>
            <FormControlLabel
              control={
                <Switch
                  checked={settings.login_enabled}
                  onChange={(e) =>
                    handleChange('login_enabled', e.target.checked)
                  }
                />
              }
              label="Enable User Login"
            />
          </Grid>
          <Grid size={{ xs: 12, md: 6 }}>
            <FormControlLabel
              control={
                <Switch
                  checked={settings.email_whitelist_enabled}
                  onChange={(e) =>
                    handleChange('email_whitelist_enabled', e.target.checked)
                  }
                />
              }
              label="Enable Email Whitelist"
            />
          </Grid>
          <Grid size={{ xs: 12, md: 6 }}>
            <FormControlLabel
              control={
                <Switch
                  checked={settings.debug_mode}
                  onChange={(e) => handleChange('debug_mode', e.target.checked)}
                  color="warning"
                />
              }
              label="Debug Mode (Requires Restart)"
            />
          </Grid>
        </Grid>
      </Paper>

      {/* Email Settings */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" gutterBottom>
          Email Settings
        </Typography>
        <Divider sx={{ mb: 3 }} />
        <Grid container spacing={3}>
          <Grid size={{ xs: 12, md: 6 }}>
            <FormControl fullWidth>
              <InputLabel>Email Backend Type</InputLabel>
              <Select
                value={settings.email_backend_type}
                label="Email Backend Type"
                onChange={(e) =>
                  handleChange('email_backend_type', e.target.value)
                }
              >
                <MenuItem value="smtp">SMTP</MenuItem>
                <MenuItem value="ses">AWS SES</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid size={{ xs: 12, md: 6 }}>
            <TextField
              fullWidth
              label="Default From Email"
              type="email"
              value={settings.default_from_email}
              onChange={(e) =>
                handleChange('default_from_email', e.target.value)
              }
            />
          </Grid>

          {settings.email_backend_type === 'smtp' && (
            <>
              <Grid size={{ xs: 12, md: 8 }}>
                <TextField
                  fullWidth
                  label="SMTP Host"
                  value={settings.email_host}
                  onChange={(e) => handleChange('email_host', e.target.value)}
                />
              </Grid>
              <Grid size={{ xs: 12, md: 4 }}>
                <TextField
                  fullWidth
                  label="SMTP Port"
                  type="number"
                  value={settings.email_port}
                  onChange={(e) =>
                    handleChange('email_port', parseInt(e.target.value))
                  }
                />
              </Grid>
              <Grid size={{ xs: 12, md: 6 }}>
                <TextField
                  fullWidth
                  label="SMTP Username"
                  value={settings.email_host_user}
                  onChange={(e) =>
                    handleChange('email_host_user', e.target.value)
                  }
                />
              </Grid>
              <Grid size={{ xs: 12, md: 6 }}>
                <TextField
                  fullWidth
                  label="SMTP Password"
                  type={showEmailPassword ? 'text' : 'password'}
                  value={settings.email_host_password}
                  onChange={(e) =>
                    handleChange('email_host_password', e.target.value)
                  }
                  InputProps={{
                    endAdornment: (
                      <InputAdornment position="end">
                        <IconButton
                          onClick={() =>
                            setShowEmailPassword(!showEmailPassword)
                          }
                          edge="end"
                        >
                          {showEmailPassword ? (
                            <VisibilityOff />
                          ) : (
                            <Visibility />
                          )}
                        </IconButton>
                      </InputAdornment>
                    ),
                  }}
                />
              </Grid>
              <Grid size={{ xs: 12, md: 6 }}>
                <FormControlLabel
                  control={
                    <Switch
                      checked={settings.email_use_tls}
                      onChange={(e) =>
                        handleChange('email_use_tls', e.target.checked)
                      }
                    />
                  }
                  label="Use TLS"
                />
              </Grid>
              <Grid size={{ xs: 12, md: 6 }}>
                <FormControlLabel
                  control={
                    <Switch
                      checked={settings.email_use_ssl}
                      onChange={(e) =>
                        handleChange('email_use_ssl', e.target.checked)
                      }
                    />
                  }
                  label="Use SSL"
                />
              </Grid>
            </>
          )}

          {settings.email_backend_type === 'ses' && (
            <Grid size={{ xs: 12, md: 6 }}>
              <TextField
                fullWidth
                label="AWS SES Region"
                value={settings.aws_ses_region}
                onChange={(e) => handleChange('aws_ses_region', e.target.value)}
                placeholder="us-east-1"
                helperText="Region for SES email service"
              />
            </Grid>
          )}

          {/* Test Email Section */}
          <Grid size={{ xs: 12 }}>
            <Divider sx={{ my: 2 }} />
            <Typography variant="subtitle1" gutterBottom>
              Test Email Configuration
            </Typography>
            <Box sx={{ display: 'flex', gap: 2, alignItems: 'flex-start' }}>
              <TextField
                label="Test Email Address"
                type="email"
                value={testEmailAddress}
                onChange={(e) => setTestEmailAddress(e.target.value)}
                placeholder="test@example.com"
                sx={{ flex: 1 }}
                helperText="Send a test email to verify your email configuration"
              />
              <Button
                variant="outlined"
                startIcon={<EmailIcon />}
                onClick={handleTestEmail}
                disabled={testingEmail || !testEmailAddress}
                sx={{ mt: 0.5 }}
              >
                {testingEmail ? 'Sending...' : 'Send Test Email'}
              </Button>
            </Box>
          </Grid>
        </Grid>
      </Paper>

      {/* AWS Settings */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" gutterBottom>
          AWS Settings
        </Typography>
        <Divider sx={{ mb: 3 }} />
        <Grid container spacing={3}>
          <Grid size={{ xs: 12, md: 6 }}>
            <FormControl fullWidth>
              <InputLabel>AWS Credential Method</InputLabel>
              <Select
                value={settings.aws_credential_method}
                label="AWS Credential Method"
                onChange={(e) =>
                  handleChange('aws_credential_method', e.target.value)
                }
              >
                <MenuItem value="profile">AWS Profile</MenuItem>
                <MenuItem value="profile_role">
                  AWS Profile + Assume Role
                </MenuItem>
                <MenuItem value="credentials_file">Credentials File</MenuItem>
                <MenuItem value="access_keys">Access Key ID + Secret</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid size={{ xs: 12, md: 6 }}>
            <TextField
              fullWidth
              label="AWS Region"
              value={settings.aws_region}
              onChange={(e) => handleChange('aws_region', e.target.value)}
              placeholder="us-east-1"
            />
          </Grid>

          {(settings.aws_credential_method === 'profile' ||
            settings.aws_credential_method === 'profile_role') && (
            <Grid size={{ xs: 12, md: 6 }}>
              <TextField
                fullWidth
                label="AWS Profile Name"
                value={settings.aws_profile_name}
                onChange={(e) =>
                  handleChange('aws_profile_name', e.target.value)
                }
                placeholder="default"
                helperText="Profile name from ~/.aws/credentials"
              />
            </Grid>
          )}

          {settings.aws_credential_method === 'profile_role' && (
            <Grid size={{ xs: 12, md: 6 }}>
              <TextField
                fullWidth
                label="AWS Role ARN"
                value={settings.aws_role_arn}
                onChange={(e) => handleChange('aws_role_arn', e.target.value)}
                placeholder="arn:aws:iam::123456789012:role/RoleName"
                helperText="Role ARN to assume"
              />
            </Grid>
          )}

          {settings.aws_credential_method === 'credentials_file' && (
            <Grid size={{ xs: 12 }}>
              <TextField
                fullWidth
                label="Credentials File Path"
                value={settings.aws_credentials_file_path}
                onChange={(e) =>
                  handleChange('aws_credentials_file_path', e.target.value)
                }
                placeholder="/path/to/credentials"
                helperText="Full path to AWS credentials file"
              />
            </Grid>
          )}

          {settings.aws_credential_method === 'access_keys' && (
            <>
              <Grid size={{ xs: 12, md: 6 }}>
                <TextField
                  fullWidth
                  label="AWS Access Key ID"
                  value={settings.aws_access_key_id}
                  onChange={(e) =>
                    handleChange('aws_access_key_id', e.target.value)
                  }
                />
              </Grid>
              <Grid size={{ xs: 12, md: 6 }}>
                <TextField
                  fullWidth
                  label="AWS Secret Access Key"
                  type={showAwsSecret ? 'text' : 'password'}
                  value={settings.aws_secret_access_key}
                  onChange={(e) =>
                    handleChange('aws_secret_access_key', e.target.value)
                  }
                  InputProps={{
                    endAdornment: (
                      <InputAdornment position="end">
                        <IconButton
                          onClick={() => setShowAwsSecret(!showAwsSecret)}
                          edge="end"
                        >
                          {showAwsSecret ? <VisibilityOff /> : <Visibility />}
                        </IconButton>
                      </InputAdornment>
                    ),
                  }}
                />
              </Grid>
            </>
          )}

          {/* Test AWS Configuration Section */}
          <Grid size={{ xs: 12 }}>
            <Divider sx={{ my: 2 }} />
            <Typography variant="subtitle1" gutterBottom>
              Test AWS Configuration
            </Typography>
            <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
              <Button
                variant="outlined"
                onClick={handleTestAws}
                disabled={testingAws}
                sx={{ minWidth: 200 }}
              >
                {testingAws ? 'Testing...' : 'Test AWS Connection'}
              </Button>
              <Typography variant="body2" color="text.secondary">
                Verify AWS credentials and role assumption using STS
              </Typography>
            </Box>
          </Grid>
        </Grid>
      </Paper>

      {/* Athena Settings */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" gutterBottom>
          Athena Historical Data Settings
        </Typography>
        <Divider sx={{ mb: 3 }} />
        <Grid container spacing={3}>
          <Grid size={{ xs: 12, md: 6 }}>
            <TextField
              fullWidth
              label="Athena Database Name"
              value={settings.athena_database_name}
              onChange={(e) =>
                handleChange('athena_database_name', e.target.value)
              }
              placeholder="forex_hist_data_db"
              helperText="AWS Athena database name for historical forex data"
            />
          </Grid>
          <Grid size={{ xs: 12, md: 6 }}>
            <TextField
              fullWidth
              label="Athena Table Name"
              value={settings.athena_table_name}
              onChange={(e) =>
                handleChange('athena_table_name', e.target.value)
              }
              placeholder="quotes"
              helperText="Athena table name for historical forex quotes"
            />
          </Grid>
          <Grid size={{ xs: 12 }}>
            <TextField
              fullWidth
              label="Athena Output S3 Bucket"
              value={settings.athena_output_bucket}
              onChange={(e) =>
                handleChange('athena_output_bucket', e.target.value)
              }
              placeholder="my-athena-results"
              helperText="S3 bucket for Athena query results (without s3:// prefix)"
            />
          </Grid>
          <Grid size={{ xs: 12 }}>
            <TextField
              fullWidth
              label="Athena Instruments"
              value={settings.athena_instruments}
              onChange={(e) =>
                handleChange('athena_instruments', e.target.value)
              }
              placeholder="EUR_USD,GBP_USD,USD_JPY"
              helperText="Comma-separated list of instruments to import from Athena"
              multiline
              rows={2}
            />
          </Grid>
          <Grid size={{ xs: 12, md: 6 }}>
            <TextField
              fullWidth
              label="Athena Query Timeout (seconds)"
              type="number"
              value={settings.athena_query_timeout}
              onChange={(e) =>
                handleChange(
                  'athena_query_timeout',
                  parseInt(e.target.value) || 600
                )
              }
              placeholder="600"
              helperText="Maximum time to wait for Athena query completion (default: 600 seconds / 10 minutes)"
              inputProps={{ min: 60, max: 3600, step: 60 }}
            />
          </Grid>

          {/* Trigger Athena Import Section */}
          <Grid size={{ xs: 12 }}>
            <Divider sx={{ my: 2 }} />
            <Typography variant="subtitle1" gutterBottom>
              Import Historical Data
            </Typography>
            <Grid container spacing={2} sx={{ mb: 2 }}>
              <Grid size={{ xs: 12, md: 6 }}>
                <TextField
                  fullWidth
                  label="Start Date"
                  type="date"
                  value={importStartDate}
                  onChange={(e) => setImportStartDate(e.target.value)}
                  InputLabelProps={{ shrink: true }}
                  helperText="Leave empty to import yesterday's data"
                />
              </Grid>
              <Grid size={{ xs: 12, md: 6 }}>
                <TextField
                  fullWidth
                  label="End Date"
                  type="date"
                  value={importEndDate}
                  onChange={(e) => setImportEndDate(e.target.value)}
                  InputLabelProps={{ shrink: true }}
                  helperText="Leave empty to import yesterday's data"
                />
              </Grid>
            </Grid>
            {/* Success Alert */}
            {importCompleted && (
              <Alert
                severity="success"
                sx={{ mb: 2 }}
                onClose={handleClearImportStatus}
              >
                <Typography variant="body2" fontWeight="medium">
                  Import completed successfully!
                </Typography>
                <Typography variant="body2">
                  {importProgress?.message ||
                    'All data has been imported from Athena.'}
                </Typography>
              </Alert>
            )}

            {/* Error Alert */}
            {importFailed && (
              <Alert
                severity="error"
                sx={{ mb: 2 }}
                action={
                  <Button
                    color="inherit"
                    size="small"
                    onClick={handleRetryImport}
                  >
                    Retry
                  </Button>
                }
              >
                <Typography variant="body2" fontWeight="medium">
                  Import failed
                </Typography>
                <Typography variant="body2">
                  {importProgress?.error ||
                    importProgress?.message ||
                    'An error occurred during the import process.'}
                </Typography>
              </Alert>
            )}

            {/* Progress Bar (only show when import is in progress) */}
            {importInProgress && importProgress && (
              <Box sx={{ mb: 3 }}>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  {importProgress.message}
                </Typography>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                  <Box sx={{ flex: 1 }}>
                    <LinearProgress
                      variant="determinate"
                      value={importProgress.percentage}
                      sx={{
                        height: 10,
                        borderRadius: 1,
                        bgcolor: 'grey.300',
                        '& .MuiLinearProgress-bar': {
                          borderRadius: 1,
                          bgcolor: 'primary.main',
                        },
                      }}
                    />
                  </Box>
                  <Typography
                    variant="body2"
                    color="text.secondary"
                    sx={{ minWidth: 50, textAlign: 'right' }}
                  >
                    {importProgress.percentage.toFixed(1)}%
                  </Typography>
                </Box>
                <Typography
                  variant="caption"
                  color="text.secondary"
                  sx={{ mt: 0.5, display: 'block' }}
                >
                  Day {importProgress.current_day} of{' '}
                  {importProgress.total_days}
                </Typography>
              </Box>
            )}
            <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
              <Button
                variant="contained"
                color="primary"
                onClick={handleTriggerAthenaImport}
                disabled={
                  triggeringImport ||
                  importInProgress ||
                  !settings.athena_output_bucket
                }
                sx={{ minWidth: 200 }}
              >
                {triggeringImport ? 'Importing...' : 'Import from Athena'}
              </Button>
              <Typography variant="body2" color="text.secondary">
                Import historical forex data from Athena for all active accounts
              </Typography>
            </Box>
          </Grid>
        </Grid>
      </Paper>

      {/* Application Settings */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" gutterBottom>
          Application Settings
        </Typography>
        <Divider sx={{ mb: 3 }} />
        <Grid container spacing={3}>
          <Grid size={{ xs: 12, md: 6 }}>
            <FormControl fullWidth>
              <InputLabel>Django Log Level (Requires Restart)</InputLabel>
              <Select
                value={settings.django_log_level}
                label="Django Log Level (Requires Restart)"
                onChange={(e) =>
                  handleChange('django_log_level', e.target.value)
                }
              >
                <MenuItem value="DEBUG">Debug</MenuItem>
                <MenuItem value="INFO">Info</MenuItem>
                <MenuItem value="WARNING">Warning</MenuItem>
                <MenuItem value="ERROR">Error</MenuItem>
                <MenuItem value="CRITICAL">Critical</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid size={{ xs: 12, md: 6 }}>
            <TextField
              fullWidth
              label="Tick Data Retention Days"
              type="number"
              value={settings.tick_data_retention_days}
              onChange={(e) =>
                handleChange(
                  'tick_data_retention_days',
                  parseInt(e.target.value)
                )
              }
              helperText="Number of days to retain tick data before cleanup"
            />
          </Grid>
          <Grid size={{ xs: 12 }}>
            <TextField
              fullWidth
              label="Tick Data Instruments"
              value={settings.tick_data_instruments}
              onChange={(e) =>
                handleChange('tick_data_instruments', e.target.value)
              }
              placeholder="EUR_USD,GBP_USD,USD_JPY"
              helperText="Comma-separated list of instruments for live tick data collection"
              multiline
              rows={2}
            />
          </Grid>
          <Grid size={{ xs: 12, md: 6 }}>
            <TextField
              fullWidth
              label="System Health Update Interval (seconds)"
              type="number"
              value={settings.system_health_update_interval}
              onChange={(e) =>
                handleChange(
                  'system_health_update_interval',
                  parseInt(e.target.value)
                )
              }
              helperText="Interval for internal system health updates (CPU, memory, etc.) (default: 5)"
            />
          </Grid>
          <Grid size={{ xs: 12, md: 6 }}>
            <TextField
              fullWidth
              label="External API Check Interval (seconds)"
              type="number"
              value={settings.external_api_check_interval}
              onChange={(e) =>
                handleChange(
                  'external_api_check_interval',
                  parseInt(e.target.value)
                )
              }
              helperText="Interval for external API health checks (e.g., OANDA API) (default: 60)"
            />
          </Grid>
          <Grid size={{ xs: 12, md: 6 }}>
            <TextField
              fullWidth
              label="OANDA Sync Interval (seconds)"
              type="number"
              value={settings.oanda_sync_interval_seconds}
              onChange={(e) =>
                handleChange(
                  'oanda_sync_interval_seconds',
                  parseInt(e.target.value)
                )
              }
              helperText="Interval for OANDA account synchronization (default: 300 = 5 minutes)"
            />
          </Grid>
          <Grid size={{ xs: 12, md: 6 }}>
            <TextField
              fullWidth
              label="OANDA Fetch Duration (days)"
              type="number"
              value={settings.oanda_fetch_duration_days}
              onChange={(e) =>
                handleChange(
                  'oanda_fetch_duration_days',
                  parseInt(e.target.value)
                )
              }
              helperText="Number of days to fetch orders and positions from OANDA (default: 365 = 1 year)"
            />
          </Grid>
          <Grid size={{ xs: 12, md: 6 }}>
            <TextField
              fullWidth
              label="Backtest CPU Limit (cores)"
              type="number"
              value={settings.backtest_cpu_limit}
              onChange={(e) =>
                handleChange(
                  'backtest_cpu_limit',
                  parseInt(e.target.value) || 1
                )
              }
              helperText="CPU core limit per backtest task (default: 1)"
              inputProps={{ min: 1, max: 16, step: 1 }}
            />
          </Grid>
          <Grid size={{ xs: 12, md: 6 }}>
            <TextField
              fullWidth
              label="Backtest Memory Limit (GB)"
              type="number"
              value={(settings.backtest_memory_limit / 1073741824).toFixed(1)}
              onChange={(e) =>
                handleChange(
                  'backtest_memory_limit',
                  Math.round(parseFloat(e.target.value) * 1073741824) ||
                    2147483648
                )
              }
              helperText="Memory limit per backtest task in GB (default: 2GB)"
              inputProps={{ min: 0.5, max: 32, step: 0.5 }}
            />
          </Grid>
        </Grid>
      </Paper>

      {/* Save Button at Bottom */}
      <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 2 }}>
        <Button
          variant="outlined"
          startIcon={<RefreshIcon />}
          onClick={fetchSettings}
          disabled={saving}
        >
          Refresh
        </Button>
        <Button
          variant="contained"
          size="large"
          startIcon={<SaveIcon />}
          onClick={handleSave}
          disabled={saving}
        >
          {saving ? 'Saving...' : 'Save Changes'}
        </Button>
      </Box>
    </Container>
  );
};

export default AdminSystemSettingsPage;
