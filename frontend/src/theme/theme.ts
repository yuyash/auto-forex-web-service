import { createTheme } from '@mui/material/styles';
import type { ThemeOptions } from '@mui/material/styles';
import { breakpoints, componentDensity, typography } from './density';

/**
 * Custom Material-UI theme configuration for the Auto Forex Trader
 * Implements responsive breakpoints and custom styling
 */

// Define color palette
const palette = {
  mode: 'light' as const,
  primary: {
    main: '#00897b',
    light: '#4ebaaa',
    dark: '#005b4f',
    contrastText: '#ffffff',
  },
  secondary: {
    main: '#dc004e',
    light: '#f50057',
    dark: '#c51162',
    contrastText: '#ffffff',
  },
  success: {
    main: '#26a69a',
    light: '#4db6ac',
    dark: '#00897b',
    contrastText: '#ffffff',
  },
  error: {
    main: '#ef5350',
    light: '#e57373',
    dark: '#d32f2f',
    contrastText: '#ffffff',
  },
  warning: {
    main: '#ff9800',
    light: '#ffb74d',
    dark: '#f57c00',
    contrastText: '#000000',
  },
  info: {
    main: '#00acc1',
    light: '#5ddef4',
    dark: '#007c91',
    contrastText: '#ffffff',
  },
  background: {
    default: '#fafafa',
    paper: '#ffffff',
  },
  text: {
    primary: 'rgba(0, 0, 0, 0.87)',
    secondary: 'rgba(0, 0, 0, 0.6)',
    disabled: 'rgba(0, 0, 0, 0.38)',
  },
};

// Define spacing
const spacing = 8;

// Define component overrides
const components = {
  MuiButton: {
    defaultProps: {
      size: 'small' as const,
    },
    styleOverrides: {
      root: {
        borderRadius: 4,
        textTransform: 'none' as const,
        fontSize: componentDensity.buttonFontSize,
        padding: componentDensity.buttonPadding,
        minHeight: componentDensity.buttonMinHeight,
        '&:focus-visible': {
          outline: '2px solid',
          outlineColor: palette.primary.main,
          outlineOffset: '2px',
        },
      },
    },
  },
  MuiIconButton: {
    defaultProps: {
      size: 'small' as const,
    },
    styleOverrides: {
      root: {
        padding: componentDensity.iconButtonPadding,
        '&:focus-visible': {
          outline: '2px solid',
          outlineColor: palette.primary.main,
          outlineOffset: '2px',
        },
      },
    },
  },
  MuiTextField: {
    defaultProps: {
      size: 'small' as const,
    },
    styleOverrides: {
      root: {
        '& .MuiInputBase-input': {
          fontSize: componentDensity.controlFontSize,
          padding: componentDensity.controlPadding,
        },
        '& .MuiInputLabel-root': {
          fontSize: componentDensity.controlFontSize,
        },
        '& .MuiOutlinedInput-root': {
          '&:focus-within': {
            outline: '2px solid',
            outlineColor: palette.primary.main,
            outlineOffset: '2px',
          },
        },
      },
    },
  },
  MuiFormControl: {
    defaultProps: {
      size: 'small' as const,
    },
  },
  MuiSelect: {
    defaultProps: {
      size: 'small' as const,
    },
  },
  MuiInputLabel: {
    defaultProps: {
      size: 'small' as const,
    },
    styleOverrides: {
      root: {
        fontSize: componentDensity.controlFontSize,
      },
    },
  },
  MuiMenuItem: {
    styleOverrides: {
      root: {
        fontSize: componentDensity.controlFontSize,
        minHeight: componentDensity.menuItemMinHeight,
        paddingTop: componentDensity.menuItemPaddingY,
        paddingBottom: componentDensity.menuItemPaddingY,
      },
    },
  },
  MuiListItemText: {
    styleOverrides: {
      primary: {
        fontSize: componentDensity.listPrimaryFontSize,
      },
      secondary: {
        fontSize: componentDensity.listSecondaryFontSize,
      },
    },
  },
  MuiListItemIcon: {
    styleOverrides: {
      root: {
        minWidth: 32,
        '& .MuiSvgIcon-root': {
          fontSize: '1.1rem',
        },
      },
    },
  },
  MuiOutlinedInput: {
    styleOverrides: {
      root: {
        fontSize: componentDensity.controlFontSize,
      },
      input: {
        padding: componentDensity.controlPadding,
      },
    },
  },
  MuiAutocomplete: {
    defaultProps: {
      size: 'small' as const,
    },
  },
  MuiChip: {
    defaultProps: {
      size: 'small' as const,
    },
  },
  MuiSwitch: {
    defaultProps: {
      size: 'small' as const,
    },
  },
  MuiCheckbox: {
    defaultProps: {
      size: 'small' as const,
    },
  },
  MuiFormControlLabel: {
    styleOverrides: {
      label: {
        fontSize: componentDensity.controlFontSize,
      },
    },
  },
  MuiRadio: {
    defaultProps: {
      size: 'small' as const,
    },
  },
  MuiFab: {
    defaultProps: {
      size: 'small' as const,
    },
  },
  MuiToggleButton: {
    defaultProps: {
      size: 'small' as const,
    },
  },
  MuiPagination: {
    defaultProps: {
      size: 'small' as const,
    },
  },
  MuiTable: {
    defaultProps: {
      size: 'small' as const,
    },
  },
  MuiCard: {
    styleOverrides: {
      root: {
        borderRadius: 8,
        boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
      },
    },
  },
  MuiPaper: {
    styleOverrides: {
      root: {
        borderRadius: 4,
      },
    },
  },
  MuiAppBar: {
    styleOverrides: {
      root: {
        boxShadow: '0 1px 3px rgba(0,0,0,0.12)',
        borderRadius: 0,
      },
    },
  },
  MuiListItemButton: {
    styleOverrides: {
      root: {
        '&:focus-visible': {
          outline: '2px solid',
          outlineColor: palette.primary.main,
          outlineOffset: '-2px',
        },
      },
    },
  },
  MuiLink: {
    styleOverrides: {
      root: {
        '&:focus-visible': {
          outline: '2px solid',
          outlineColor: palette.primary.main,
          outlineOffset: '2px',
          borderRadius: '2px',
        },
      },
    },
  },
  // MUI X Charts configuration
  MuiChartsAxis: {
    styleOverrides: {
      root: {
        '& .MuiChartsAxis-line': {
          stroke: 'rgba(0, 0, 0, 0.12)',
        },
        '& .MuiChartsAxis-tick': {
          stroke: 'rgba(0, 0, 0, 0.12)',
        },
        '& .MuiChartsAxis-tickLabel': {
          fill: 'rgba(0, 0, 0, 0.6)',
          fontSize: '0.75rem',
        },
      },
    },
  },
  MuiChartsGrid: {
    styleOverrides: {
      root: {
        '& .MuiChartsGrid-line': {
          stroke: 'rgba(0, 0, 0, 0.06)',
          strokeDasharray: '3 3',
        },
      },
    },
  },
  MuiChartsTooltip: {
    styleOverrides: {
      root: {
        backgroundColor: 'rgba(255, 255, 255, 0.95)',
        border: '1px solid rgba(0, 0, 0, 0.12)',
        borderRadius: 4,
        boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
        padding: '8px 12px',
      },
      table: {
        '& td': {
          padding: '2px 8px',
          fontSize: '0.875rem',
        },
      },
    },
  },
  MuiChartsLegend: {
    styleOverrides: {
      root: {
        '& .MuiChartsLegend-series': {
          fontSize: '0.875rem',
        },
      },
    },
  },
};

// Create theme options
const themeOptions: ThemeOptions = {
  breakpoints,
  palette,
  typography,
  spacing,
  components,
};

// Create and export the theme
const theme = createTheme(themeOptions);

export default theme;
