export const breakpoints = {
  values: {
    xs: 0,
    sm: 600,
    md: 960,
    lg: 1280,
    xl: 1920,
  },
};

export const layoutTokens = {
  pagePadding: { xs: 1.5, sm: 2, md: 3 },
  sectionGap: { xs: 1.5, sm: 2 },
  toolbarGap: 1,
  chartCardHeight: { xs: 240, sm: 260 },
  contentMaxWidth: 1600,
} as const;

export const fontFamily = [
  '-apple-system',
  'BlinkMacSystemFont',
  '"Segoe UI"',
  'Roboto',
  '"Helvetica Neue"',
  'Arial',
  'sans-serif',
  '"Apple Color Emoji"',
  '"Segoe UI Emoji"',
  '"Segoe UI Symbol"',
].join(',');

export const typography = {
  fontFamily,
  h1: {
    fontSize: '2.5rem',
    fontWeight: 500,
    lineHeight: 1.2,
  },
  h2: {
    fontSize: '2rem',
    fontWeight: 500,
    lineHeight: 1.3,
  },
  h3: {
    fontSize: '1.75rem',
    fontWeight: 500,
    lineHeight: 1.4,
  },
  h4: {
    fontSize: '1.5rem',
    fontWeight: 500,
    lineHeight: 1.4,
  },
  h5: {
    fontSize: '1.25rem',
    fontWeight: 500,
    lineHeight: 1.5,
  },
  h6: {
    fontSize: '1rem',
    fontWeight: 500,
    lineHeight: 1.6,
  },
  body1: {
    fontSize: '0.875rem',
    lineHeight: 1.5,
  },
  body2: {
    fontSize: '0.875rem',
    lineHeight: 1.43,
  },
  button: {
    fontSize: '0.875rem',
    fontWeight: 500,
    textTransform: 'none' as const,
  },
  caption: {
    fontSize: '0.75rem',
    lineHeight: 1.66,
  },
  overline: {
    fontSize: '0.75rem',
    fontWeight: 500,
    lineHeight: 2.66,
    textTransform: 'uppercase' as const,
  },
};

export const componentDensity = {
  buttonFontSize: '0.8125rem',
  buttonMinHeight: 32,
  buttonPadding: '4px 10px',
  controlFontSize: '0.8125rem',
  controlPadding: '6px 10px',
  iconButtonPadding: 5,
  listPrimaryFontSize: '0.8125rem',
  listSecondaryFontSize: '0.75rem',
  menuItemMinHeight: 32,
  menuItemPaddingY: 4,
} as const;
