/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */

/**
 * Serializer for public account settings (no authentication required).
 */
export type PublicAccountSettings = {
  /**
   * Whether new user registration is enabled
   */
  registration_enabled?: boolean;
  /**
   * Whether user login is enabled
   */
  login_enabled?: boolean;
  /**
   * Whether email whitelist is enforced for registration/login
   */
  email_whitelist_enabled?: boolean;
};
