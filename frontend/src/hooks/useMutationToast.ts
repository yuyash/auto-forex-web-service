import { useToast } from '../components/common/useToast';

interface MutationToastOptions {
  successMessage?: string;
  errorMessage?: string;
  loadingMessage?: string;
}

/**
 * Hook for showing toast notifications for mutations
 * Provides consistent messaging for create, update, delete operations
 */
export const useMutationToast = () => {
  const toast = useToast();

  const showMutationToast = {
    create: (entityName: string, options?: MutationToastOptions) => ({
      onSuccess: () => {
        toast.showSuccess(
          options?.successMessage || `${entityName} created successfully`
        );
      },
      onError: (error: unknown) => {
        const err = error as { response?: { data?: { message?: string } } };
        const message =
          err?.response?.data?.message ||
          options?.errorMessage ||
          `Failed to create ${entityName}`;
        toast.showError(message);
      },
    }),

    update: (entityName: string, options?: MutationToastOptions) => ({
      onSuccess: () => {
        toast.showSuccess(
          options?.successMessage || `${entityName} updated successfully`
        );
      },
      onError: (error: unknown) => {
        const err = error as { response?: { data?: { message?: string } } };
        const message =
          err?.response?.data?.message ||
          options?.errorMessage ||
          `Failed to update ${entityName}`;
        toast.showError(message);
      },
    }),

    delete: (entityName: string, options?: MutationToastOptions) => ({
      onSuccess: () => {
        toast.showSuccess(
          options?.successMessage || `${entityName} deleted successfully`
        );
      },
      onError: (error: unknown) => {
        const err = error as { response?: { data?: { message?: string } } };
        const message =
          err?.response?.data?.message ||
          options?.errorMessage ||
          `Failed to delete ${entityName}`;
        toast.showError(message);
      },
    }),

    action: (actionName: string, options?: MutationToastOptions) => ({
      onSuccess: () => {
        toast.showSuccess(
          options?.successMessage || `${actionName} completed successfully`
        );
      },
      onError: (error: unknown) => {
        const err = error as { response?: { data?: { message?: string } } };
        const message =
          err?.response?.data?.message ||
          options?.errorMessage ||
          `Failed to ${actionName}`;
        toast.showError(message);
      },
    }),
  };

  return {
    ...toast,
    showMutationToast,
  };
};
