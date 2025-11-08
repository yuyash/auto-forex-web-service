import { Box, Link } from '@mui/material';

/**
 * Skip links for keyboard navigation accessibility
 * Allows keyboard users to skip to main content or navigation
 */
const SkipLinks = () => {
  return (
    <Box
      sx={{
        position: 'absolute',
        left: '-9999px',
        zIndex: 9999,
        '&:focus-within': {
          left: 0,
          top: 0,
          width: '100%',
          backgroundColor: 'primary.main',
          color: 'primary.contrastText',
          padding: 2,
          display: 'flex',
          gap: 2,
          justifyContent: 'center',
        },
      }}
    >
      <Link
        href="#main-content"
        sx={{
          color: 'inherit',
          textDecoration: 'underline',
          '&:focus': {
            outline: '2px solid',
            outlineColor: 'primary.contrastText',
            outlineOffset: '2px',
          },
        }}
      >
        Skip to main content
      </Link>
      <Link
        href="#navigation"
        sx={{
          color: 'inherit',
          textDecoration: 'underline',
          '&:focus': {
            outline: '2px solid',
            outlineColor: 'primary.contrastText',
            outlineOffset: '2px',
          },
        }}
      >
        Skip to navigation
      </Link>
    </Box>
  );
};

export default SkipLinks;
