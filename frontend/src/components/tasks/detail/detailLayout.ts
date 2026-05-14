import { layoutTokens } from '../../../theme/density';

export const taskDetailLayout = {
  container: {
    py: { xs: 0.75, sm: 1 },
    px: { xs: 0.75, sm: 1.25 },
    display: 'flex',
    flexDirection: 'column',
    flex: '1 0 auto',
    minHeight: 0,
    overflow: 'visible',
    width: '100%',
    maxWidth: `var(--app-content-max-width, ${layoutTokens.contentMaxWidth}px)`,
    mx: 'auto',
  },
  tabPaper: {
    mb: 1,
    display: 'flex',
    flexDirection: 'column',
    flex: '1 0 auto',
    minHeight: 0,
    overflow: 'visible',
  },
} as const;
