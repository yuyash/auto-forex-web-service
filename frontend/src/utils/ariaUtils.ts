/**
 * ARIA utilities for accessibility
 */

/**
 * Generate a unique ID for ARIA relationships
 */
export const generateAriaId = (prefix: string): string => {
  return `${prefix}-${Math.random().toString(36).substr(2, 9)}`;
};

/**
 * Get ARIA label for task status
 */
export const getStatusAriaLabel = (status: string): string => {
  const statusLabels: Record<string, string> = {
    created: 'Task created, not yet started',
    starting: 'Task is starting',
    running: 'Task is currently running',
    paused: 'Task is paused',
    stopping: 'Task is stopping',
    stopped: 'Task has been stopped',
    completed: 'Task completed successfully',
    failed: 'Task failed with errors',
  };

  return statusLabels|| status;
};

/**
 * Get ARIA label for progress indicator
 */
export const getProgressAriaLabel = (
  progress: number,
  status: string
): string => {
  if (status === 'completed') {
    return 'Task completed, 100% progress';
  }
  if (status === 'failed') {
    return 'Task failed';
  }
  return `Task progress: ${progress}% complete`;
};

/**
 * Get ARIA label for action button
 */
export const getActionAriaLabel = (
  action: string,
  itemName?: string
): string => {
  const actionLabels: Record<string, string> = {
    start: 'Start',
    stop: 'Stop',
    pause: 'Pause',
    resume: 'Resume',
    rerun: 'Rerun',
    copy: 'Copy',
    edit: 'Edit',
    delete: 'Delete',
    view: 'View details',
  };

  const label = actionLabels[action] || action;
  return itemName ? `${label} ${itemName}` : label;
};

/**
 * Get ARIA label for navigation item
 */
export const getNavigationAriaLabel = (
  label: string,
  isActive: boolean
): string => {
  return isActive ? `${label} (current page)` : label;
};

/**
 * Get ARIA label for form field
 */
export const getFormFieldAriaLabel = (
  label: string,
  required: boolean,
  error?: string
): string => {
  let ariaLabel = label;
  if (required) {
    ariaLabel += ', required';
  }
  if (error) {
    ariaLabel += `, error: ${error}`;
  }
  return ariaLabel;
};

/**
 * Get ARIA live region politeness level
 */
export const getAriaLive = (
  severity: 'info' | 'success' | 'warning' | 'error'
): 'polite' | 'assertive' => {
  return severity === 'error' || severity === 'warning'
    ? 'assertive'
    : 'polite';
};

/**
 * Get ARIA role for component
 */
export const getAriaRole = (componentType: string): string | undefined => {
  const roleMap: Record<string, string> = {
    card: 'article',
    list: 'list',
    listItem: 'listitem',
    navigation: 'navigation',
    main: 'main',
    complementary: 'complementary',
    banner: 'banner',
    contentinfo: 'contentinfo',
    search: 'search',
    form: 'form',
    dialog: 'dialog',
    alertdialog: 'alertdialog',
    alert: 'alert',
    status: 'status',
    progressbar: 'progressbar',
    tab: 'tab',
    tabpanel: 'tabpanel',
    tablist: 'tablist',
  };

  return roleMap[componentType];
};

/**
 * Create ARIA description for complex components
 */
export const createAriaDescription = (parts: string[]): string => {
  return parts.filter(Boolean).join('. ');
};

/**
 * Get ARIA label for chart
 */
export const getChartAriaLabel = (
  chartType: string,
  dataPoints: number,
  summary?: string
): string => {
  let label = `${chartType} chart with ${dataPoints} data points`;
  if (summary) {
    label += `. ${summary}`;
  }
  return label;
};

/**
 * Get ARIA label for table
 */
export const getTableAriaLabel = (
  tableName: string,
  rowCount: number,
  columnCount: number
): string => {
  return `${tableName} table with ${rowCount} rows and ${columnCount} columns`;
};

/**
 * Get ARIA label for pagination
 */
export const getPaginationAriaLabel = (
  currentPage: number,
  totalPages: number
): string => {
  return `Page ${currentPage} of ${totalPages}`;
};

/**
 * Get ARIA label for sort button
 */
export const getSortAriaLabel = (
  column: string,
  direction?: 'asc' | 'desc'
): string => {
  if (!direction) {
    return `Sort by ${column}`;
  }
  const directionLabel = direction === 'asc' ? 'ascending' : 'descending';
  return `Sorted by ${column}, ${directionLabel}. Click to change sort direction`;
};

/**
 * Get ARIA label for filter
 */
export const getFilterAriaLabel = (
  filterName: string,
  activeCount: number
): string => {
  if (activeCount === 0) {
    return `${filterName} filter, no filters active`;
  }
  return `${filterName} filter, ${activeCount} ${
    activeCount === 1 ? 'filter' : 'filters'
  } active`;
};
