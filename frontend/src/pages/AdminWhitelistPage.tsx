import { useState, useEffect } from 'react';
import {
  Container,
  Typography,
  Box,
  Paper,
  Button,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Switch,
  FormControlLabel,
  Alert,
  CircularProgress,
  Chip,
} from '@mui/material';
import {
  Add as AddIcon,
  Delete as DeleteIcon,
  Edit as EditIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';
import { useAuth } from '../contexts/AuthContext';
import { Breadcrumbs } from '../components/common';
import { useToast } from '../components/common/useToast';

interface WhitelistedEmail {
  id: number;
  email_pattern: string;
  description: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

const AdminWhitelistPage = () => {
  const { token } = useAuth();
  const { showSuccess, showError } = useToast();
  const [loading, setLoading] = useState(true);
  const [emails, setEmails] = useState<WhitelistedEmail[]>([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingEmail, setEditingEmail] = useState<WhitelistedEmail | null>(
    null
  );
  const [formData, setFormData] = useState({
    email_pattern: '',
    description: '',
    is_active: true,
  });

  const fetchEmails = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/admin/whitelist/emails', {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error('Failed to fetch whitelisted emails');
      }

      const data = await response.json();
      setEmails(data);
    } catch (error) {
      showError('Failed to load whitelisted emails');
      console.error('Error fetching emails:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchEmails();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const handleOpenDialog = (email?: WhitelistedEmail) => {
    if (email) {
      setEditingEmail(email);
      setFormData({
        email_pattern: email.email_pattern,
        description: email.description,
        is_active: email.is_active,
      });
    } else {
      setEditingEmail(null);
      setFormData({
        email_pattern: '',
        description: '',
        is_active: true,
      });
    }
    setDialogOpen(true);
  };

  const handleCloseDialog = () => {
    setDialogOpen(false);
    setEditingEmail(null);
    setFormData({
      email_pattern: '',
      description: '',
      is_active: true,
    });
  };

  const handleSave = async () => {
    try {
      const url = editingEmail
        ? `/api/admin/whitelist/emails/${editingEmail.id}`
        : '/api/admin/whitelist/emails';
      const method = editingEmail ? 'PUT' : 'POST';

      const response = await fetch(url, {
        method,
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(formData),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(
          error.error || error.email_pattern?.[0] || 'Failed to save'
        );
      }

      showSuccess(
        editingEmail
          ? 'Email pattern updated successfully'
          : 'Email pattern added successfully'
      );
      handleCloseDialog();
      fetchEmails();
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : 'Failed to save email pattern';
      showError(errorMessage);
      console.error('Error saving email:', error);
    }
  };

  const handleDelete = async (id: number) => {
    if (
      !window.confirm('Are you sure you want to delete this email pattern?')
    ) {
      return;
    }

    try {
      const response = await fetch(`/api/admin/whitelist/emails/${id}`, {
        method: 'DELETE',
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error('Failed to delete email pattern');
      }

      showSuccess('Email pattern deleted successfully');
      fetchEmails();
    } catch (error) {
      showError('Failed to delete email pattern');
      console.error('Error deleting email:', error);
    }
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
          <Typography variant="h4">Email Whitelist</Typography>
          <Box sx={{ display: 'flex', gap: 2 }}>
            <Button
              variant="outlined"
              startIcon={<RefreshIcon />}
              onClick={fetchEmails}
            >
              Refresh
            </Button>
            <Button
              variant="contained"
              startIcon={<AddIcon />}
              onClick={() => handleOpenDialog()}
            >
              Add Email Pattern
            </Button>
          </Box>
        </Box>
        <Typography variant="body2" color="text.secondary">
          Manage email patterns that are allowed to register and login
        </Typography>
      </Box>

      <Alert severity="info" sx={{ mb: 3 }}>
        Email patterns can be specific addresses (user@example.com) or domain
        wildcards (*@example.com or @example.com). Enable Email Whitelist in
        System Settings to enforce these restrictions.
      </Alert>

      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Email Pattern</TableCell>
              <TableCell>Description</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Created</TableCell>
              <TableCell align="right">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {emails.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} align="center">
                  <Typography
                    variant="body2"
                    color="text.secondary"
                    sx={{ py: 4 }}
                  >
                    No email patterns configured. Click "Add Email Pattern" to
                    get started.
                  </Typography>
                </TableCell>
              </TableRow>
            ) : (
              emails.map((email) => (
                <TableRow key={email.id}>
                  <TableCell>
                    <Typography variant="body2" fontFamily="monospace">
                      {email.email_pattern}
                    </Typography>
                  </TableCell>
                  <TableCell>{email.description || '-'}</TableCell>
                  <TableCell>
                    <Chip
                      label={email.is_active ? 'Active' : 'Inactive'}
                      color={email.is_active ? 'success' : 'default'}
                      size="small"
                    />
                  </TableCell>
                  <TableCell>
                    {new Date(email.created_at).toLocaleDateString()}
                  </TableCell>
                  <TableCell align="right">
                    <IconButton
                      size="small"
                      onClick={() => handleOpenDialog(email)}
                      color="primary"
                    >
                      <EditIcon />
                    </IconButton>
                    <IconButton
                      size="small"
                      onClick={() => handleDelete(email.id)}
                      color="error"
                    >
                      <DeleteIcon />
                    </IconButton>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </TableContainer>

      {/* Add/Edit Dialog */}
      <Dialog
        open={dialogOpen}
        onClose={handleCloseDialog}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>
          {editingEmail ? 'Edit Email Pattern' : 'Add Email Pattern'}
        </DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 2, display: 'flex', flexDirection: 'column', gap: 3 }}>
            <TextField
              fullWidth
              label="Email Pattern"
              value={formData.email_pattern}
              onChange={(e) =>
                setFormData({ ...formData, email_pattern: e.target.value })
              }
              placeholder="user@example.com or *@example.com"
              helperText="Specific email or domain wildcard (*@example.com)"
            />
            <TextField
              fullWidth
              label="Description"
              value={formData.description}
              onChange={(e) =>
                setFormData({ ...formData, description: e.target.value })
              }
              placeholder="Optional description"
              multiline
              rows={2}
            />
            <FormControlLabel
              control={
                <Switch
                  checked={formData.is_active}
                  onChange={(e) =>
                    setFormData({ ...formData, is_active: e.target.checked })
                  }
                />
              }
              label="Active"
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDialog}>Cancel</Button>
          <Button
            onClick={handleSave}
            variant="contained"
            disabled={!formData.email_pattern}
          >
            {editingEmail ? 'Update' : 'Add'}
          </Button>
        </DialogActions>
      </Dialog>
    </Container>
  );
};

export default AdminWhitelistPage;
