import { useWrappedMutation } from './useWrappedMutation';
import {
  authApi,
  type LoginRequest,
  type LoginResponse,
  type RegisterRequest,
  type RegisterResponse,
} from '../services/api/auth';

export function useLogin(options?: {
  onSuccess?: (data: LoginResponse) => void;
  onError?: (error: Error) => void;
}) {
  return useWrappedMutation(
    (variables: LoginRequest) => authApi.login(variables),
    {
      onSuccess: (data) => options?.onSuccess?.(data),
      onError: (error) => options?.onError?.(error),
    }
  );
}

export function useRegister(options?: {
  onSuccess?: (data: RegisterResponse) => void;
  onError?: (error: Error) => void;
}) {
  return useWrappedMutation(
    (variables: RegisterRequest) => authApi.register(variables),
    {
      onSuccess: (data) => options?.onSuccess?.(data),
      onError: (error) => options?.onError?.(error),
    }
  );
}
