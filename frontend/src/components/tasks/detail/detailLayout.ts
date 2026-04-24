import { layoutTokens } from '../../../theme/density';

export const taskDetailLayout = {
  container: {
    py: { xs: 2, sm: 3 },
    px: { xs: 1, sm: 2 },
    display: 'flex',
    flexDirection: 'column',
    flex: 1,
    minHeight: 0,
    overflow: 'hidden',
    width: '100%',
    maxWidth: layoutTokens.contentMaxWidth,
    mx: 'auto',
  },
  tabPaper: {
    mb: 1,
    display: 'flex',
    flexDirection: 'column',
    flex: 1,
    minHeight: 0,
    overflow: 'hidden',
  },
} as const;
