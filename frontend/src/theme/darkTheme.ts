import { createTheme } from '@mui/material/styles';
import type { ThemeOptions } from '@mui/material/styles';
import { breakpoints, componentDensity, typography } from './density';

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

const components = {
  MuiCssBaseline: {
    styleOverrides: {
      body: {
        scrollbarColor: `${palette.divider} ${palette.background.default}`,
        '&::-webkit-scrollbar, & *::-webkit-scrollbar': {
          width: 8,
          height: 8,
          backgroundColor: palette.background.default,
        },
        '&::-webkit-scrollbar-thumb, & *::-webkit-scrollbar-thumb': {
          borderRadius: 4,
          backgroundColor: palette.divider,
          border: `2px solid ${palette.background.default}`,
        },
        '&::-webkit-scrollbar-thumb:hover, & *::-webkit-scrollbar-thumb:hover':
          {
            backgroundColor: palette.text.secondary,
          },
        '&::-webkit-scrollbar-track, & *::-webkit-scrollbar-track': {
          backgroundColor: palette.background.default,
        },
      },
    },
  },
  MuiButton: {
    defaultProps: { size: 'small' as const },
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
    defaultProps: { size: 'small' as const },
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
    defaultProps: { size: 'small' as const },
    styleOverrides: {
      root: {
        '& .MuiInputBase-input': {
          fontSize: componentDensity.controlFontSize,
          padding: componentDensity.controlPadding,
        },
        '& .MuiInputLabel-root': {
          fontSize: componentDensity.controlFontSize,
        },
      },
    },
  },
  MuiFormControl: { defaultProps: { size: 'small' as const } },
  MuiSelect: { defaultProps: { size: 'small' as const } },
  MuiInputLabel: {
    defaultProps: { size: 'small' as const },
    styleOverrides: { root: { fontSize: componentDensity.controlFontSize } },
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
      primary: { fontSize: componentDensity.listPrimaryFontSize },
      secondary: { fontSize: componentDensity.listSecondaryFontSize },
    },
  },
  MuiListItemIcon: {
    styleOverrides: {
      root: { minWidth: 32, '& .MuiSvgIcon-root': { fontSize: '1.1rem' } },
    },
  },
  MuiOutlinedInput: {
    styleOverrides: {
      root: { fontSize: componentDensity.controlFontSize },
      input: { padding: componentDensity.controlPadding },
    },
  },
  MuiAutocomplete: { defaultProps: { size: 'small' as const } },
  MuiChip: { defaultProps: { size: 'small' as const } },
  MuiSwitch: { defaultProps: { size: 'small' as const } },
  MuiCheckbox: { defaultProps: { size: 'small' as const } },
  MuiFormControlLabel: {
    styleOverrides: { label: { fontSize: componentDensity.controlFontSize } },
  },
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
  MuiAlert: {
    styleOverrides: {
      standardInfo: {
        color: palette.text.primary,
        '& .MuiAlert-icon': {
          color: palette.info.main,
        },
      },
      standardWarning: {
        color: palette.text.primary,
        '& .MuiAlert-icon': {
          color: palette.warning.main,
        },
      },
      standardError: {
        color: palette.text.primary,
        '& .MuiAlert-icon': {
          color: palette.error.main,
        },
      },
      standardSuccess: {
        color: palette.text.primary,
        '& .MuiAlert-icon': {
          color: palette.success.main,
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
