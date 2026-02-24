/**
 * Strategy configuration schemas.
 *
 * Previously, each strategy's full schema was hardcoded here. Now the
 * backend JSON schema (e.g. `backend/apps/trading/schemas/floor.json`)
 * is the single source of truth — it includes group, title, description,
 * default, dependsOn, and all other UI metadata.
 *
 * The API endpoint `GET /api/trading/strategies/` returns the schema in
 * `config_schema`, and `StrategyConfigForm` renders it automatically.
 *
 * This map is kept only as an optional override layer. If a strategy ID
 * is present here, the frontend schema takes precedence over the API one
 * (useful for rapid prototyping before the backend schema is updated).
 *
 * For most strategies, this map should be empty — the backend schema is
 * sufficient.
 */
import type { ConfigSchema } from '../../types/strategy';

export const STRATEGY_CONFIG_SCHEMAS: Record<string, ConfigSchema> = {
  // No overrides needed — backend schemas include all UI metadata
  // (group, title, description, default, dependsOn, etc.)
};
