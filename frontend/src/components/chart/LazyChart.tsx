// Lazy-loaded chart wrapper to reduce initial bundle size
import { lazy, Suspense, type ComponentType } from 'react';
import { Box, Skeleton } from '@mui/material';

// Lazy load chart components
const FinancialChart = lazy(() =>
  import('./FinancialChart').then((m) => ({ default: m.FinancialChart }))
);

// Chart loading fallback
function ChartLoadingFallback() {
  return (
    <Box
      sx={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        minHeight: 400,
        width: '100%',
      }}
    >
      <Skeleton
        variant="rectangular"
        width="100%"
        height={400}
        animation="wave"
        aria-label="Loading chart"
      />
    </Box>
  );
}

// Lazy chart wrapper with suspense
interface LazyChartWrapperProps {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  component: ComponentType<any>;
  fallback?: React.ReactNode;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  [key: string]: any;
}

export function LazyChartWrapper({
  component: Component,
  fallback = <ChartLoadingFallback />,
  ...props
}: LazyChartWrapperProps) {
  return (
    <Suspense fallback={fallback}>
      <Component {...props} />
    </Suspense>
  );
}

// Pre-configured lazy chart components
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const LazyFinancialChart = (props: any) => (
  <LazyChartWrapper component={FinancialChart} {...props} />
);

export default LazyChartWrapper;
