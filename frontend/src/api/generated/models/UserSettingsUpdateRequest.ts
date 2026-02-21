/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { LanguageEnum } from './LanguageEnum';
/**
 * Serializer for updating user settings.
 */
export type UserSettingsUpdateRequest = {
  timezone?: string;
  language?: LanguageEnum;
  first_name?: string;
  last_name?: string;
  username?: string;
  notification_enabled?: boolean;
  notification_email?: boolean;
  notification_browser?: boolean;
  settings_json?: any;
};
