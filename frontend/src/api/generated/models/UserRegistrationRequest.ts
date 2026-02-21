/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * Serializer for user registration.
 */
export type UserRegistrationRequest = {
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
  /**
   * Password must be at least 8 characters long
   */
  password: string;
  /**
   * Confirm password
   */
  password_confirm: string;
};
