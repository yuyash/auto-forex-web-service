import React from 'react';
import ErrorBoundary from './ErrorBoundary';

interface PageErrorBoundaryProps {
  children: React.ReactNode;
}

/**
 * Page-level error boundary that catches errors within a specific page
 * and provides recovery options without crashing the entire app
 */
const PageErrorBoundary: React.FC<PageErrorBoundaryProps> = ({ children }) => {
  const handleReset = () => {
    // Reload the current page
    window.location.reload();
  };

  const handleError = (error: Error) => {
    // Log page-level errors
    console.error('Page error:', error);
  };

  return (
    <ErrorBoundary level="page" onReset={handleReset} onError={handleError}>
      {children}
    </ErrorBoundary>
  );
};

export default PageErrorBoundary;
