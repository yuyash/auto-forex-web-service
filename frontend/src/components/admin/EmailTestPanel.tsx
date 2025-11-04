import React, { useState } from 'react';
import {
  Paper,
  Typography,
  Box,
  TextField,
  Button,
  Alert,
  CircularProgress,
  Divider,
  List,
  ListItem,
  ListItemText,
} from '@mui/material';
import { Send as SendIcon, CheckCircle, Error } from '@mui/icons-material';
import { useAuth } from '../../contexts/AuthContext';

interface EmailConfiguration {
  backend: string;
  host: string;
  port: number;
  use_tls: boolean;
  from_email: string;
}

interface TestEmailResponse {
  success: boolean;
  message?: string;
  error?: string;
  configuration: EmailConfiguration;
}

const EmailTestPanel: React.FC = () => {
  const { token } = useAuth();
  const [testEmail, setTestEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<TestEmailResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleTestEmail = async () => {
    if (!token || !testEmail) return;

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await fetch('/api/admin/test-email', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ test_email: testEmail }),
      });

      const data = await response.json();

      if (response.ok) {
        setResult(data);
      } else {
        setError(data.error || 'Failed to send test email');
        if (data.configuration) {
          setResult(data);
        }
      }
    } catch (err) {
      const errorMessage =
        err && typeof err === 'object' && 'message' in err
          ? String(err.message)
          : 'Failed to send test email';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (event: React.KeyboardEvent) => {
    if (event.key === 'Enter' && !loading) {
      handleTestEmail();
    }
  };

  return (
    <Paper elevation={2} sx={{ p: 3 }}>
      <Typography variant="h6" gutterBottom>
        Email Configuration Test
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        Send a test email to verify your email configuration is working
        correctly
      </Typography>

      <Box sx={{ mb: 3 }}>
        <TextField
          fullWidth
          label="Test Email Address"
          type="email"
          value={testEmail}
          onChange={(e) => setTestEmail(e.target.value)}
          onKeyPress={handleKeyPress}
          disabled={loading}
          placeholder="Enter email address to send test email"
          helperText="A test email will be sent to this address"
        />
      </Box>

      <Button
        variant="contained"
        color="primary"
        onClick={handleTestEmail}
        disabled={loading || !testEmail}
        startIcon={loading ? <CircularProgress size={20} /> : <SendIcon />}
        fullWidth
      >
        {loading ? 'Sending Test Email...' : 'Send Test Email'}
      </Button>

      {error && (
        <Alert severity="error" sx={{ mt: 3 }} icon={<Error />}>
          {error}
        </Alert>
      )}

      {result && (
        <Box sx={{ mt: 3 }}>
          {result.success ? (
            <Alert severity="success" icon={<CheckCircle />}>
              {result.message}
            </Alert>
          ) : (
            <Alert severity="error" icon={<Error />}>
              {result.error}
            </Alert>
          )}

          <Divider sx={{ my: 2 }} />

          <Typography variant="subtitle2" gutterBottom>
            Current Email Configuration:
          </Typography>
          <List dense>
            <ListItem>
              <ListItemText
                primary="Backend"
                secondary={result.configuration.backend}
              />
            </ListItem>
            <ListItem>
              <ListItemText
                primary="SMTP Host"
                secondary={result.configuration.host}
              />
            </ListItem>
            <ListItem>
              <ListItemText
                primary="SMTP Port"
                secondary={result.configuration.port}
              />
            </ListItem>
            <ListItem>
              <ListItemText
                primary="Use TLS"
                secondary={result.configuration.use_tls ? 'Yes' : 'No'}
              />
            </ListItem>
            <ListItem>
              <ListItemText
                primary="From Email"
                secondary={result.configuration.from_email}
              />
            </ListItem>
          </List>

          {!result.success && (
            <Alert severity="info" sx={{ mt: 2 }}>
              Please check your email configuration in the backend settings
              (.env file) and ensure:
              <ul>
                <li>EMAIL_HOST is correct</li>
                <li>EMAIL_PORT is correct</li>
                <li>EMAIL_HOST_USER and EMAIL_HOST_PASSWORD are set</li>
                <li>EMAIL_USE_TLS or EMAIL_USE_SSL is configured properly</li>
                <li>DEFAULT_FROM_EMAIL is a valid email address</li>
              </ul>
            </Alert>
          )}
        </Box>
      )}
    </Paper>
  );
};

export default EmailTestPanel;
