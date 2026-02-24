import { createTheme } from '@mui/material/styles';
import type { ThemeOptions } from '@mui/material/styles';

/**
 * Dark theme for Auto Forex Trader.
 * TradingView-inspired dark palette with the same component overrides.
 */

const palette = {
  mode: 'dark' as const,
  primary: {
    main: '#4db6ac',
    light: '#82e9de',
    dark: '#00867d',
    contrastText: '#000000',
  },
  secondary: {
    main: '#f48fb1',
    light: '#ffc1e3',
    dark: '#bf5f82',
    contrastText: '#000000',
  },
  success: {
    main: '#26a69a',
    light: '#64d8cb',
    dark: '#00766c',
    contrastText: '#000000',
  },
  error: {
    main: '#ef5350',
    light: '#ff867c',
    dark: '#b61827',
    contrastText: '#ffffff',
  },
  warning: {
    main: '#ffa726',
    light: '#ffd95b',
    dark: '#c77800',
    contrastText: '#000000',
  },
  info: {
    main: '#4dd0e1',
    light: '#88ffff',
    dark: '#009faf',
    contrastText: '#000000',
  },
  background: {
    default: '#131722',
    paper: '#1e222d',
  },
  text: {
    primary: '#d1d4dc',
    secondary: '#787b86',
    disabled: '#4c525e',
  },
  divider: '#2a2e39',
};

const breakpoints = {
  values: { xs: 0, sm: 600, md: 960, lg: 1280, xl: 1920 },
};

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
  h1: { fontSize: '2.5rem', fontWeight: 500, lineHeight: 1.2 },
  h2: { fontSize: '2rem', fontWeight: 500, lineHeight: 1.3 },
  h3: { fontSize: '1.75rem', fontWeight: 500, lineHeight: 1.4 },
  h4: { fontSize: '1.5rem', fontWeight: 500, lineHeight: 1.4 },
  h5: { fontSize: '1.25rem', fontWeight: 500, lineHeight: 1.5 },
  h6: { fontSize: '1rem', fontWeight: 500, lineHeight: 1.6 },
  body1: { fontSize: '1rem', lineHeight: 1.5 },
  body2: { fontSize: '0.875rem', lineHeight: 1.43 },
  button: {
    fontSize: '0.875rem',
    fontWeight: 500,
    textTransform: 'none' as const,
  },
  caption: { fontSize: '0.75rem', lineHeight: 1.66 },
  overline: {
    fontSize: '0.75rem',
    fontWeight: 500,
    lineHeight: 2.66,
    textTransform: 'uppercase' as const,
  },
};

const components = {
  MuiButton: {
    defaultProps: { size: 'small' as const },
    styleOverrides: {
      root: {
        borderRadius: 4,
        textTransform: 'none' as const,
        fontSize: '0.8rem',
        padding: '3px 10px',
        minHeight: 30,
        '&:focus-visible': {
          outline: '2px solid',
          outlineColor: palette.primary.main,
          outlineOffset: '2px',
        },
      },
    },
  },
  MuiIconButton: {
    defaultProps: { size: 'small' as const },
    styleOverrides: {
      root: {
        padding: 4,
        '&:focus-visible': {
          outline: '2px solid',
          outlineColor: palette.primary.main,
          outlineOffset: '2px',
        },
      },
    },
  },
  MuiTextField: {
    defaultProps: { size: 'small' as const },
    styleOverrides: {
      root: {
        '& .MuiInputBase-input': { fontSize: '0.8rem', padding: '6px 10px' },
        '& .MuiInputLabel-root': { fontSize: '0.8rem' },
      },
    },
  },
  MuiFormControl: { defaultProps: { size: 'small' as const } },
  MuiSelect: { defaultProps: { size: 'small' as const } },
  MuiInputLabel: {
    defaultProps: { size: 'small' as const },
    styleOverrides: { root: { fontSize: '0.8rem' } },
  },
  MuiMenuItem: {
    styleOverrides: {
      root: {
        fontSize: '0.75rem',
        minHeight: 28,
        paddingTop: 2,
        paddingBottom: 2,
      },
    },
  },
  MuiListItemText: {
    styleOverrides: {
      primary: { fontSize: '0.75rem' },
      secondary: { fontSize: '0.65rem' },
    },
  },
  MuiListItemIcon: {
    styleOverrides: {
      root: { minWidth: 32, '& .MuiSvgIcon-root': { fontSize: '1.1rem' } },
    },
  },
  MuiOutlinedInput: {
    styleOverrides: {
      root: { fontSize: '0.8rem' },
      input: { padding: '6px 10px' },
    },
  },
  MuiAutocomplete: { defaultProps: { size: 'small' as const } },
  MuiChip: { defaultProps: { size: 'small' as const } },
  MuiSwitch: { defaultProps: { size: 'small' as const } },
  MuiCheckbox: { defaultProps: { size: 'small' as const } },
  MuiFormControlLabel: { styleOverrides: { label: { fontSize: '0.75rem' } } },
  MuiRadio: { defaultProps: { size: 'small' as const } },
  MuiFab: { defaultProps: { size: 'small' as const } },
  MuiToggleButton: { defaultProps: { size: 'small' as const } },
  MuiPagination: { defaultProps: { size: 'small' as const } },
  MuiTable: { defaultProps: { size: 'small' as const } },
  MuiCard: {
    styleOverrides: {
      root: { borderRadius: 8, boxShadow: '0 2px 8px rgba(0,0,0,0.4)' },
    },
  },
  MuiPaper: {
    styleOverrides: { root: { borderRadius: 4, backgroundImage: 'none' } },
  },
  MuiAppBar: {
    styleOverrides: {
      root: { boxShadow: '0 1px 3px rgba(0,0,0,0.4)', borderRadius: 0 },
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
};

const themeOptions: ThemeOptions = {
  breakpoints,
  palette,
  typography,
  spacing: 8,
  components,
};

const darkTheme = createTheme(themeOptions);

export default darkTheme;
