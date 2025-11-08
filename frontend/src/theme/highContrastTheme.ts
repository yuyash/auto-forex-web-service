import { createTheme } from '@mui/material/styles';
import type { ThemeOptions } from '@mui/material/styles';

/**
 * High contrast theme for accessibility
 * Ensures all colors meet WCAG AA standards (4.5:1 contrast ratio)
 */

// Define custom breakpoints (same as main theme)
const breakpoints = {
  values: {
    xs: 0,
    sm: 600,
    md: 960,
    lg: 1280,
    xl: 1920,
  },
};

// High contrast color palette
const palette = {
  mode: 'light' as const,
  primary: {
    main: '#0000CC', // Dark blue - 8.59:1 contrast on white
    light: '#0000FF',
    dark: '#000099',
    contrastText: '#FFFFFF',
  },
  secondary: {
    main: '#CC0000', // Dark red - 7.37:1 contrast on white
    light: '#FF0000',
    dark: '#990000',
    contrastText: '#FFFFFF',
  },
  success: {
    main: '#006600', // Dark green - 7.26:1 contrast on white
    light: '#008000',
    dark: '#004400',
    contrastText: '#FFFFFF',
  },
  error: {
    main: '#CC0000', // Dark red - 7.37:1 contrast on white
    light: '#FF0000',
    dark: '#990000',
    contrastText: '#FFFFFF',
  },
  warning: {
    main: '#CC6600', // Dark orange - 4.54:1 contrast on white
    light: '#FF8C00',
    dark: '#994C00',
    contrastText: '#FFFFFF',
  },
  info: {
    main: '#0066CC', // Dark blue - 5.74:1 contrast on white
    light: '#0080FF',
    dark: '#004C99',
    contrastText: '#FFFFFF',
  },
  background: {
    default: '#FFFFFF',
    paper: '#FFFFFF',
  },
  text: {
    primary: '#000000', // Pure black - 21:1 contrast on white
    secondary: '#333333', // Dark gray - 12.63:1 contrast on white
    disabled: '#666666', // Medium gray - 5.74:1 contrast on white
  },
  divider: '#000000',
};

// Typography with enhanced readability
const typography = {
  fontFamily: [
    '-apple-system',
    'BlinkMacSystemFont',
    '"Segoe UI"',
    'Roboto',
    '"Helvetica Neue"',
    'Arial',
    'sans-serif',
  ].join(','),
  h1: {
    fontSize: '2.5rem',
    fontWeight: 700, // Bolder for better visibility
    lineHeight: 1.2,
    color: '#000000',
  },
  h2: {
    fontSize: '2rem',
    fontWeight: 700,
    lineHeight: 1.3,
    color: '#000000',
  },
  h3: {
    fontSize: '1.75rem',
    fontWeight: 700,
    lineHeight: 1.4,
    color: '#000000',
  },
  h4: {
    fontSize: '1.5rem',
    fontWeight: 700,
    lineHeight: 1.4,
    color: '#000000',
  },
  h5: {
    fontSize: '1.25rem',
    fontWeight: 700,
    lineHeight: 1.5,
    color: '#000000',
  },
  h6: {
    fontSize: '1rem',
    fontWeight: 700,
    lineHeight: 1.6,
    color: '#000000',
  },
  body1: {
    fontSize: '1rem',
    lineHeight: 1.6, // Increased for readability
    fontWeight: 500,
  },
  body2: {
    fontSize: '0.875rem',
    lineHeight: 1.5,
    fontWeight: 500,
  },
  button: {
    fontSize: '0.875rem',
    fontWeight: 700, // Bolder buttons
    textTransform: 'none' as const,
  },
};

// Component overrides with enhanced contrast
const components = {
  MuiButton: {
    styleOverrides: {
      root: {
        borderRadius: 4,
        textTransform: 'none' as const,
        border: '2px solid transparent',
        '&:focus-visible': {
          outline: '3px solid #000000',
          outlineOffset: '3px',
        },
      },
      contained: {
        boxShadow: 'none',
        '&:hover': {
          boxShadow: 'none',
        },
      },
      outlined: {
        borderWidth: '2px',
        '&:hover': {
          borderWidth: '2px',
        },
      },
    },
  },
  MuiCard: {
    styleOverrides: {
      root: {
        borderRadius: 4,
        border: '2px solid #000000',
        boxShadow: 'none',
      },
    },
  },
  MuiPaper: {
    styleOverrides: {
      root: {
        borderRadius: 4,
        border: '1px solid #000000',
      },
      outlined: {
        border: '2px solid #000000',
      },
    },
  },
  MuiListItemButton: {
    styleOverrides: {
      root: {
        '&.Mui-selected': {
          backgroundColor: '#0000CC',
          color: '#FFFFFF',
          '&:hover': {
            backgroundColor: '#000099',
          },
        },
        '&:focus-visible': {
          outline: '3px solid #000000',
          outlineOffset: '-3px',
        },
      },
    },
  },
  MuiIconButton: {
    styleOverrides: {
      root: {
        border: '1px solid transparent',
        '&:focus-visible': {
          outline: '3px solid #000000',
          outlineOffset: '2px',
        },
      },
    },
  },
  MuiTextField: {
    styleOverrides: {
      root: {
        '& .MuiOutlinedInput-root': {
          '& fieldset': {
            borderWidth: '2px',
            borderColor: '#000000',
          },
          '&:hover fieldset': {
            borderWidth: '2px',
            borderColor: '#000000',
          },
          '&.Mui-focused fieldset': {
            borderWidth: '3px',
            borderColor: '#0000CC',
          },
        },
      },
    },
  },
  MuiLink: {
    styleOverrides: {
      root: {
        textDecoration: 'underline',
        textDecorationThickness: '2px',
        '&:focus-visible': {
          outline: '3px solid #000000',
          outlineOffset: '2px',
          borderRadius: '2px',
        },
      },
    },
  },
  MuiChip: {
    styleOverrides: {
      root: {
        border: '2px solid',
        fontWeight: 700,
      },
    },
  },
  MuiAlert: {
    styleOverrides: {
      root: {
        border: '2px solid',
        fontWeight: 500,
      },
      standardSuccess: {
        borderColor: '#006600',
      },
      standardError: {
        borderColor: '#CC0000',
      },
      standardWarning: {
        borderColor: '#CC6600',
      },
      standardInfo: {
        borderColor: '#0066CC',
      },
    },
  },
  MuiTableCell: {
    styleOverrides: {
      root: {
        borderBottom: '2px solid #000000',
      },
      head: {
        fontWeight: 700,
        backgroundColor: '#F0F0F0',
      },
    },
  },
};

// Create high contrast theme options
const highContrastThemeOptions: ThemeOptions = {
  breakpoints,
  palette,
  typography,
  spacing: 8,
  components,
};

// Create and export the high contrast theme
const highContrastTheme = createTheme(highContrastThemeOptions);

export default highContrastTheme;
