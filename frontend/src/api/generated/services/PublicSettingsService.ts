/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { PublicAccountSettings } from '../models/PublicAccountSettings';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class PublicSettingsService {
  /**
   * GET /api/accounts/settings/public
   * Retrieve public account settings including registration and login availability. No authentication required.
   * @returns PublicAccountSettings Public settings retrieved successfully
   * @throws ApiError
   */
  public static accountsSettingsPublicRetrieve(): CancelablePromise<PublicAccountSettings> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/accounts/settings/public',
    });
  }
}
