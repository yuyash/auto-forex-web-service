/**
 * Focus management utilities for accessibility
 */

/**
 * Trap focus within a container element
 * Useful for modals and dialogs
 */
export const trapFocus = (container: HTMLElement) => {
  const focusableElements = container.querySelectorAll<HTMLElement>(
    'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
  );

  const firstFocusable = focusableElements[0];
  const lastFocusable = focusableElements[focusableElements.length - 1];

  const handleKeyDown = (event: KeyboardEvent) => {
    if (event.key !== 'Tab') return;

    if (event.shiftKey) {
      // Shift + Tab
      if (document.activeElement === firstFocusable) {
        event.preventDefault();
        lastFocusable?.focus();
      }
    } else {
      // Tab
      if (document.activeElement === lastFocusable) {
        event.preventDefault();
        firstFocusable?.focus();
      }
    }
  };

  container.addEventListener('keydown', handleKeyDown);

  // Focus first element
  firstFocusable?.focus();

  // Return cleanup function
  return () => {
    container.removeEventListener('keydown', handleKeyDown);
  };
};

/**
 * Get all focusable elements within a container
 */
export const getFocusableElements = (container: HTMLElement): HTMLElement[] => {
  const elements = container.querySelectorAll<HTMLElement>(
    'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
  );
  return Array.from(elements);
};

/**
 * Focus the first focusable element in a container
 */
export const focusFirstElement = (container: HTMLElement): void => {
  const focusableElements = getFocusableElements(container);
  focusableElements[0]?.focus();
};

/**
 * Focus the last focusable element in a container
 */
export const focusLastElement = (container: HTMLElement): void => {
  const focusableElements = getFocusableElements(container);
  focusableElements[focusableElements.length - 1]?.focus();
};

/**
 * Save current focus and return a function to restore it
 */
export const saveFocus = (): (() => void) => {
  const activeElement = document.activeElement as HTMLElement;

  return () => {
    activeElement?.focus();
  };
};

/**
 * Check if an element is focusable
 */
export const isFocusable = (element: HTMLElement): boolean => {
  const focusableSelectors = [
    'button:not([disabled])',
    '[href]',
    'input:not([disabled])',
    'select:not([disabled])',
    'textarea:not([disabled])',
    '[tabindex]:not([tabindex="-1"])',
  ];

  return focusableSelectors.some((selector) => element.matches(selector));
};

/**
 * Move focus to next focusable element
 */
export const focusNext = (container: HTMLElement = document.body): void => {
  const focusableElements = getFocusableElements(container);
  const currentIndex = focusableElements.findIndex(
    (el) => el === document.activeElement
  );

  if (currentIndex === -1) {
    focusableElements[0]?.focus();
  } else {
    const nextIndex = (currentIndex + 1) % focusableElements.length;
    focusableElements[nextIndex]?.focus();
  }
};

/**
 * Move focus to previous focusable element
 */
export const focusPrevious = (container: HTMLElement = document.body): void => {
  const focusableElements = getFocusableElements(container);
  const currentIndex = focusableElements.findIndex(
    (el) => el === document.activeElement
  );

  if (currentIndex === -1) {
    focusableElements[focusableElements.length - 1]?.focus();
  } else {
    const prevIndex =
      currentIndex === 0 ? focusableElements.length - 1 : currentIndex - 1;
    focusableElements[prevIndex]?.focus();
  }
};

/**
 * Create a focus trap hook for React components
 * Note: Import useEffect from 'react' in your component to use this
 */
export const createFocusTrapEffect = (
  containerRef: React.RefObject<HTMLElement>,
  isActive: boolean
) => {
  if (!isActive || !containerRef.current) return;

  const cleanup = trapFocus(containerRef.current);
  return cleanup;
};
