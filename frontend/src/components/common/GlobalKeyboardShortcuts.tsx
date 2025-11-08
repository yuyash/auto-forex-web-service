import { useEffect, useState, useMemo } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  Typography,
  Box,
  IconButton,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Chip,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import { getModifierKeyLabel } from '../tasks/actions/useKeyboardShortcuts';

interface GlobalShortcut {
  keys: string[];
  description: string;
  action: () => void;
  category: 'Navigation' | 'Actions' | 'Help';
}

/**
 * Global keyboard shortcuts component
 * Provides application-wide keyboard navigation and shortcuts
 */
const GlobalKeyboardShortcuts = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [helpDialogOpen, setHelpDialogOpen] = useState(false);

  const shortcuts: GlobalShortcut[] = useMemo(
    () => [
      // Navigation shortcuts
      {
        keys: ['g', 'd'],
        description: 'Go to Dashboard',
        action: () => navigate('/dashboard'),
        category: 'Navigation',
      },
      {
        keys: ['g', 'c'],
        description: 'Go to Configurations',
        action: () => navigate('/configurations'),
        category: 'Navigation',
      },
      {
        keys: ['g', 'b'],
        description: 'Go to Backtest Tasks',
        action: () => navigate('/backtest-tasks'),
        category: 'Navigation',
      },
      {
        keys: ['g', 't'],
        description: 'Go to Trading Tasks',
        action: () => navigate('/trading-tasks'),
        category: 'Navigation',
      },
      {
        keys: ['g', 's'],
        description: 'Go to Settings',
        action: () => navigate('/settings'),
        category: 'Navigation',
      },
      // Action shortcuts
      {
        keys: ['n'],
        description: 'New item (context-dependent)',
        action: () => {
          if (location.pathname === '/configurations') {
            navigate('/configurations/new');
          } else if (location.pathname === '/backtest-tasks') {
            navigate('/backtest-tasks/new');
          } else if (location.pathname === '/trading-tasks') {
            navigate('/trading-tasks/new');
          }
        },
        category: 'Actions',
      },
      {
        keys: ['Escape'],
        description: 'Close dialog or go back',
        action: () => {
          // This will be handled by individual components
        },
        category: 'Actions',
      },
      // Help shortcuts
      {
        keys: ['?'],
        description: 'Show keyboard shortcuts',
        action: () => setHelpDialogOpen(true),
        category: 'Help',
      },
    ],
    [navigate, location.pathname]
  );

  useEffect(() => {
    let keySequence: string[] = [];
    let sequenceTimeout: ReturnType<typeof setTimeout>;

    const handleKeyDown = (event: KeyboardEvent) => {
      // Don't trigger shortcuts when typing in input fields
      const target = event.target as HTMLElement;
      if (
        target.tagName === 'INPUT' ||
        target.tagName === 'TEXTAREA' ||
        target.isContentEditable
      ) {
        return;
      }

      // Handle single key shortcuts
      if (event.key === '?') {
        event.preventDefault();
        setHelpDialogOpen(true);
        return;
      }

      if (event.key === 'Escape') {
        // Let individual components handle Escape
        return;
      }

      // Handle key sequences (like 'g' then 'd')
      keySequence.push(event.key.toLowerCase());

      // Clear sequence after 1 second
      clearTimeout(sequenceTimeout);
      sequenceTimeout = setTimeout(() => {
        keySequence = [];
      }, 1000);

      // Check if sequence matches any shortcut
      for (const shortcut of shortcuts) {
        if (
          shortcut.keys.length === keySequence.length &&
          shortcut.keys.every((key, index) => key === keySequence[index])
        ) {
          event.preventDefault();
          shortcut.action();
          keySequence = [];
          break;
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      clearTimeout(sequenceTimeout);
    };
  }, [shortcuts]);

  const groupedShortcuts = shortcuts.reduce(
    (acc, shortcut) => {
      if (!acc[shortcut.category]) {
        acc[shortcut.category] = [];
      }
      acc[shortcut.category].push(shortcut);
      return acc;
    },
    {} as Record<string, GlobalShortcut[]>
  );

  return (
    <Dialog
      open={helpDialogOpen}
      onClose={() => setHelpDialogOpen(false)}
      maxWidth="md"
      fullWidth
      aria-labelledby="keyboard-shortcuts-dialog-title"
    >
      <DialogTitle id="keyboard-shortcuts-dialog-title">
        <Box display="flex" justifyContent="space-between" alignItems="center">
          <Typography variant="h6">Keyboard Shortcuts</Typography>
          <IconButton
            aria-label="close"
            onClick={() => setHelpDialogOpen(false)}
            size="small"
          >
            <CloseIcon />
          </IconButton>
        </Box>
      </DialogTitle>
      <DialogContent>
        {Object.entries(groupedShortcuts).map(
          ([category, categoryShortcuts]) => (
            <Box key={category} mb={3}>
              <Typography variant="subtitle1" fontWeight="bold" mb={1}>
                {category}
              </Typography>
              <TableContainer component={Paper} variant="outlined">
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Shortcut</TableCell>
                      <TableCell>Description</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {categoryShortcuts.map((shortcut, index) => (
                      <TableRow key={index}>
                        <TableCell>
                          <Box display="flex" gap={0.5}>
                            {shortcut.keys.map((key, keyIndex) => (
                              <Chip
                                key={keyIndex}
                                label={key.toUpperCase()}
                                size="small"
                                sx={{
                                  fontFamily: 'monospace',
                                  fontWeight: 'bold',
                                }}
                              />
                            ))}
                          </Box>
                        </TableCell>
                        <TableCell>{shortcut.description}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </Box>
          )
        )}

        <Box mt={3}>
          <Typography variant="subtitle2" color="text.secondary">
            Task-specific shortcuts (when viewing a task):
          </Typography>
          <TableContainer component={Paper} variant="outlined" sx={{ mt: 1 }}>
            <Table size="small">
              <TableBody>
                <TableRow>
                  <TableCell>
                    <Chip
                      label={`${getModifierKeyLabel()} + S`}
                      size="small"
                      sx={{ fontFamily: 'monospace', fontWeight: 'bold' }}
                    />
                  </TableCell>
                  <TableCell>Start task</TableCell>
                </TableRow>
                <TableRow>
                  <TableCell>
                    <Chip
                      label={`${getModifierKeyLabel()} + X`}
                      size="small"
                      sx={{ fontFamily: 'monospace', fontWeight: 'bold' }}
                    />
                  </TableCell>
                  <TableCell>Stop task</TableCell>
                </TableRow>
                <TableRow>
                  <TableCell>
                    <Chip
                      label={`${getModifierKeyLabel()} + P`}
                      size="small"
                      sx={{ fontFamily: 'monospace', fontWeight: 'bold' }}
                    />
                  </TableCell>
                  <TableCell>Pause task</TableCell>
                </TableRow>
                <TableRow>
                  <TableCell>
                    <Chip
                      label={`${getModifierKeyLabel()} + R`}
                      size="small"
                      sx={{ fontFamily: 'monospace', fontWeight: 'bold' }}
                    />
                  </TableCell>
                  <TableCell>Rerun task</TableCell>
                </TableRow>
                <TableRow>
                  <TableCell>
                    <Chip
                      label={`${getModifierKeyLabel()} + D`}
                      size="small"
                      sx={{ fontFamily: 'monospace', fontWeight: 'bold' }}
                    />
                  </TableCell>
                  <TableCell>Copy task</TableCell>
                </TableRow>
                <TableRow>
                  <TableCell>
                    <Chip
                      label={`${getModifierKeyLabel()} + E`}
                      size="small"
                      sx={{ fontFamily: 'monospace', fontWeight: 'bold' }}
                    />
                  </TableCell>
                  <TableCell>Edit task</TableCell>
                </TableRow>
                <TableRow>
                  <TableCell>
                    <Chip
                      label="Delete"
                      size="small"
                      sx={{ fontFamily: 'monospace', fontWeight: 'bold' }}
                    />
                  </TableCell>
                  <TableCell>Delete task</TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </TableContainer>
        </Box>
      </DialogContent>
    </Dialog>
  );
};

export default GlobalKeyboardShortcuts;
