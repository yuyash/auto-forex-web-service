/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */

import type { ApiTypeEnum } from './ApiTypeEnum';
import type { JurisdictionEnum } from './JurisdictionEnum';
/**
 * Serializer for OANDA account.
 */
export type OandaAccounts = {
  readonly id: number;
  /**
   * OANDA account ID
   */
  account_id: string;
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
   * Current account balance
   */
  readonly balance: string;
  /**
   * Margin currently used by open positions
   */
  readonly margin_used: string;
  /**
   * Margin available for new positions
   */
  readonly margin_available: string;
  /**
   * Unrealized profit/loss from open positions
   */
  readonly unrealized_pnl: string;
  /**
   * Whether the account is active
   */
  is_active?: boolean;
  /**
   * Whether this is the default account for market data collection
   */
  is_default?: boolean;
  /**
   * Timestamp when the account was added
   */
  readonly created_at: string;
  /**
   * Timestamp when the account was last updated
   */
  readonly updated_at: string;
};
