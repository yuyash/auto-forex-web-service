/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * Serializer for user registration.
 */
export type UserRegistration = {
  /**
   * User's email address (used for login)
   */
  email: string;
  /**
   * Username (auto-generated from email if not provided)
   */
  username?: string;
  first_name?: string;
  last_name?: string;
};
