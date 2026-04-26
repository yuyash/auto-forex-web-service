import { Container, type ContainerProps } from '@mui/material';
import { layoutTokens } from '../../theme/density';

export default function PageContainer({ sx, ...props }: ContainerProps) {
  const sxArray = Array.isArray(sx) ? sx : sx ? [sx] : [];

  return (
    <Container
      maxWidth={false}
      {...props}
      sx={[
        {
          width: '100%',
          maxWidth: `var(--app-content-max-width, ${layoutTokens.contentMaxWidth}px)`,
          mx: 'auto',
          px: layoutTokens.pagePadding,
        },
        ...sxArray,
      ]}
    />
  );
}
