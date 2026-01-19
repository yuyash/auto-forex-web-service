/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { UserLogin } from '../models/UserLogin';
import type { UserLoginRequest } from '../models/UserLoginRequest';
import type { UserRegistration } from '../models/UserRegistration';
import type { UserRegistrationRequest } from '../models/UserRegistrationRequest';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class AccountsService {
  /**
   * /api/accounts/
   * @returns any No response body
   * @throws ApiError
   */
  public static accountsRetrieve(): CancelablePromise<any> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/accounts/',
    });
  }
  /**
   * /api/accounts/auth/login
   * Handle user login.
   * @param requestBody
   * @returns UserLogin
   * @throws ApiError
   */
  public static accountsAuthLoginCreate(
    requestBody: UserLoginRequest
  ): CancelablePromise<UserLogin> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/accounts/auth/login',
      body: requestBody,
      mediaType: 'application/json',
    });
  }
  /**
   * /api/accounts/auth/logout
   * Handle user logout.
   * @returns any No response body
   * @throws ApiError
   */
  public static accountsAuthLogoutCreate(): CancelablePromise<any> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/accounts/auth/logout',
    });
  }
  /**
   * /api/accounts/auth/refresh
   * Handle token refresh.
   * @returns any No response body
   * @throws ApiError
   */
  public static accountsAuthRefreshCreate(): CancelablePromise<any> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/accounts/auth/refresh',
    });
  }
  /**
   * /api/accounts/auth/register
   * Handle user registration.
   * @param requestBody
   * @returns UserRegistration
   * @throws ApiError
   */
  public static accountsAuthRegisterCreate(
    requestBody: UserRegistrationRequest
  ): CancelablePromise<UserRegistration> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/accounts/auth/register',
      body: requestBody,
      mediaType: 'application/json',
    });
  }
  /**
   * /api/accounts/auth/resend-verification
   * Resend verification email.
   * @returns any No response body
   * @throws ApiError
   */
  public static accountsAuthResendVerificationCreate(): CancelablePromise<any> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/accounts/auth/resend-verification',
    });
  }
  /**
   * /api/accounts/auth/verify-email
   * Verify user email with token.
   * @returns any No response body
   * @throws ApiError
   */
  public static accountsAuthVerifyEmailCreate(): CancelablePromise<any> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/accounts/auth/verify-email',
    });
  }
  /**
   * /api/accounts/notifications
   * Get list of notifications for the authenticated user.
   * @returns any No response body
   * @throws ApiError
   */
  public static accountsNotificationsRetrieve(): CancelablePromise<any> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/accounts/notifications',
    });
  }
  /**
   * /api/accounts/notifications/{notification_id}/read
   * Mark a notification as read.
   * @param notificationId
   * @returns any No response body
   * @throws ApiError
   */
  public static accountsNotificationsReadCreate(
    notificationId: number
  ): CancelablePromise<any> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/accounts/notifications/{notification_id}/read',
      path: {
        notification_id: notificationId,
      },
    });
  }
  /**
   * /api/accounts/notifications/read-all
   * Mark all unread notifications as read.
   * @returns any No response body
   * @throws ApiError
   */
  public static accountsNotificationsReadAllCreate(): CancelablePromise<any> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/accounts/notifications/read-all',
    });
  }
  /**
   * /api/accounts/settings/
   * Get user settings.
   * @returns any No response body
   * @throws ApiError
   */
  public static accountsSettingsRetrieve(): CancelablePromise<any> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/accounts/settings/',
    });
  }
  /**
   * /api/accounts/settings/
   * Update user settings.
   * @returns any No response body
   * @throws ApiError
   */
  public static accountsSettingsUpdate(): CancelablePromise<any> {
    return __request(OpenAPI, {
      method: 'PUT',
      url: '/api/accounts/settings/',
    });
  }
  /**
   * /api/accounts/settings/public
   * Get public account settings.
   * @returns any No response body
   * @throws ApiError
   */
  public static accountsSettingsPublicRetrieve(): CancelablePromise<any> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/accounts/settings/public',
    });
  }
}
