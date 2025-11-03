import '@mui/material/styles';

/**
 * Extend Material-UI theme types to include custom breakpoints
 */
declare module '@mui/material/styles' {
  interface BreakpointOverrides {
    xs: true;
    sm: true;
    md: true;
    lg: true;
    xl: true;
  }
}
