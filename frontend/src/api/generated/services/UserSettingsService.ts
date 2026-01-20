/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class UserSettingsService {
  /**
   * GET /api/accounts/settings/
   * Retrieve user profile and settings including timezone, language, and notification preferences.
   * @returns any
   * @throws ApiError
   */
  public static accountsSettingsRetrieve(): CancelablePromise<{
    user?: {
      id?: number;
      username?: string;
      email?: string;
      first_name?: string;
      last_name?: string;
    };
    settings?: {
      timezone?: string;
      language?: string;
      notifications_enabled?: boolean;
    };
  }> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/accounts/settings/',
      errors: {
        401: `Authentication required`,
      },
    });
  }
  /**
   * PUT /api/accounts/settings/
   * Update user profile and settings. Can update timezone, language, notification preferences, etc.
   * @param requestBody
   * @returns any Settings updated successfully
   * @throws ApiError
   */
  public static accountsSettingsUpdate(
    requestBody?: Record<string, any>
  ): CancelablePromise<any> {
    return __request(OpenAPI, {
      method: 'PUT',
      url: '/api/accounts/settings/',
      body: requestBody,
      mediaType: 'type',
      errors: {
        400: `Validation error`,
        401: `Authentication required`,
      },
    });
  }
}
