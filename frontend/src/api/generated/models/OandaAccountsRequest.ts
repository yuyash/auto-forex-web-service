/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { ApiTypeEnum } from './ApiTypeEnum';
import type { JurisdictionEnum } from './JurisdictionEnum';
/**
 * Serializer for OANDA account.
 */
export type OandaAccountsRequest = {
  /**
   * OANDA account ID
   */
  account_id: string;
  /**
   * OANDA API token (will be encrypted)
   */
  api_token: string;
  /**
   * API endpoint type (practice or live)
   *
   * * `practice` - Practice
   * * `live` - Live
   */
  api_type?: ApiTypeEnum;
  /**
   * Regulatory jurisdiction for this account
   *
   * * `US` - United States
   * * `JP` - Japan
   * * `OTHER` - Other/International
   */
  jurisdiction?: JurisdictionEnum;
  /**
   * Account base currency
   */
  currency?: string;
  /**
   * Whether the account is active
   */
  is_active?: boolean;
  /**
   * Whether this is the default account for market data collection
   */
  is_default?: boolean;
};
