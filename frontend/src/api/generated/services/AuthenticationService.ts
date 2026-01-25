/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { EmailVerificationRequest } from '../models/EmailVerificationRequest';
import type { ResendVerificationRequest } from '../models/ResendVerificationRequest';
import type { UserLoginRequest } from '../models/UserLoginRequest';
import type { UserRegistrationRequest } from '../models/UserRegistrationRequest';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class AuthenticationService {
  /**
   * POST /api/accounts/auth/login
   * Authenticate user with email and password. Returns JWT token on success. Rate limited to 5 attempts per 15 minutes per IP address.
   * @param requestBody
   * @returns any Login successful
   * @throws ApiError
   */
  public static accountsAuthLoginCreate(
    requestBody: UserLoginRequest
  ): CancelablePromise<{
    token?: string;
    user?: {
      id?: number;
      email?: string;
      username?: string;
      is_staff?: boolean;
      timezone?: string;
      language?: string;
    };
  }> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/accounts/auth/login',
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        401: `Invalid credentials`,
        403: `Account locked or email not whitelisted`,
        429: `Too many failed login attempts`,
        503: `Login is disabled`,
      },
    });
  }
  /**
   * POST /api/accounts/auth/logout
   * Logout user and terminate all active sessions. Requires valid JWT token in Authorization header.
   * @returns any Logout successful
   * @throws ApiError
   */
  public static accountsAuthLogoutCreate(): CancelablePromise<{
    message?: string;
    sessions_terminated?: number;
  }> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/accounts/auth/logout',
      errors: {
        401: `Invalid or expired token`,
      },
    });
  }
  /**
   * POST /api/accounts/auth/refresh
   * Refresh an existing JWT token to extend its expiration time. Requires valid JWT token in Authorization header.
   * @returns any Token refreshed successfully
   * @throws ApiError
   */
  public static accountsAuthRefreshCreate(): CancelablePromise<{
    token?: string;
    user?: {
      id?: number;
      email?: string;
      username?: string;
      is_staff?: boolean;
      timezone?: string;
      language?: string;
    };
  }> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/accounts/auth/refresh',
      errors: {
        401: `Invalid or expired token`,
        500: `Failed to retrieve user information`,
      },
    });
  }
  /**
   * POST /api/accounts/auth/register
   * Register a new user account and send email verification link.
   * @param requestBody
   * @returns any User registered successfully
   * @throws ApiError
   */
  public static accountsAuthRegisterCreate(
    requestBody: UserRegistrationRequest
  ): CancelablePromise<{
    message?: string;
    user?: {
      id?: number;
      email?: string;
      username?: string;
      first_name?: string;
      last_name?: string;
      email_verified?: boolean;
    };
    email_sent?: boolean;
  }> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/accounts/auth/register',
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        400: `Validation error`,
        503: `Registration is disabled`,
      },
    });
  }
  /**
   * POST /api/accounts/auth/resend-verification
   * Resend email verification link to the specified email address.
   * @param requestBody
   * @returns any Verification email sent
   * @throws ApiError
   */
  public static accountsAuthResendVerificationCreate(
    requestBody: ResendVerificationRequest
  ): CancelablePromise<any> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/accounts/auth/resend-verification',
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        400: `Email is required or already verified`,
      },
    });
  }
  /**
   * POST /api/accounts/auth/verify-email
   * Verify user email address using the verification token sent via email.
   * @param requestBody
   * @returns any Email verified successfully
   * @throws ApiError
   */
  public static accountsAuthVerifyEmailCreate(
    requestBody: EmailVerificationRequest
  ): CancelablePromise<any> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/accounts/auth/verify-email',
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        400: `Invalid or expired token`,
      },
    });
  }
}
