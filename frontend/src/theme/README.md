# Theme Configuration

This directory contains the Material-UI theme configuration for the Auto Forex Trader.

## Breakpoints

The theme uses custom responsive breakpoints:

- **xs**: 0px - Extra small devices (phones)
- **sm**: 600px - Small devices (tablets)
- **md**: 960px - Medium devices (small laptops)
- **lg**: 1280px - Large devices (desktops)
- **xl**: 1920px - Extra large devices (large desktops)

## Usage

### Importing the theme

```typescript
import theme from './theme/theme';
// or
import { theme } from './theme';
```

### Using breakpoints in components

```typescript
import { useTheme, useMediaQuery } from '@mui/material';

function MyComponent() {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  const isTablet = useMediaQuery(theme.breakpoints.between('sm', 'md'));
  const isDesktop = useMediaQuery(theme.breakpoints.up('md'));

  return <div>{isMobile ? 'Mobile View' : 'Desktop View'}</div>;
}
```

### Using breakpoints in sx prop

```typescript
<Box
  sx={{
    width: {
      xs: '100%', // 0-599px
      sm: '80%', // 600-959px
      md: '60%', // 960-1279px
      lg: '50%', // 1280-1919px
      xl: '40%', // 1920px+
    },
    padding: {
      xs: 1, // 8px
      sm: 2, // 16px
      md: 3, // 24px
    },
  }}
>
  Content
</Box>
```

### Using breakpoints in styled components

```typescript
import { styled } from '@mui/material/styles';

const ResponsiveBox = styled(Box)(({ theme }) => ({
  padding: theme.spacing(1),
  [theme.breakpoints.up('sm')]: {
    padding: theme.spacing(2),
  },
  [theme.breakpoints.up('md')]: {
    padding: theme.spacing(3),
  },
  [theme.breakpoints.up('lg')]: {
    padding: theme.spacing(4),
  },
}));
```

## Color Palette

The theme includes a comprehensive color palette:

- **Primary**: Blue (#1976d2) - Main brand color
- **Secondary**: Pink (#dc004e) - Accent color
- **Success**: Teal (#26a69a) - Positive actions/states
- **Error**: Red (#ef5350) - Errors and warnings
- **Warning**: Orange (#ff9800) - Caution states
- **Info**: Blue (#2196f3) - Informational messages

## Typography

The theme uses a system font stack for optimal performance and native feel:

- Font Family: System fonts (San Francisco, Segoe UI, Roboto, etc.)
- Headings: h1-h6 with appropriate sizes and weights
- Body: body1 (1rem) and body2 (0.875rem)
- Button: 0.875rem with medium weight
- Caption: 0.75rem for small text

## Component Overrides

The theme includes custom styling for common components:

- **Buttons**: Rounded corners, no text transform
- **Cards**: Rounded corners with subtle shadow
- **Papers**: Rounded corners
- **AppBar**: Subtle shadow

## Requirements

This theme configuration satisfies the following requirements:

- **38.1**: Responsive design using Material-UI breakpoints
- **38.2**: Mobile-optimized layout for screens < 600px
- **38.3**: Desktop layout for screens > 960px
