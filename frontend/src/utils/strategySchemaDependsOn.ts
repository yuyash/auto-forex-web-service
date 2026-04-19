/**
 * Shared helpers for evaluating strategy JSON-schema `dependsOn` conditions.
 *
 * The backend schema lets a property declare a `dependsOn` block:
 *
 *   {
 *     "dependsOn": {
 *       "field": "stop_loss_enabled",
 *       "values": [true],
 *       "and": [...]   // all must match in addition to the root
 *       "or":  [...]   // any of these alternative branches may match
 *     }
 *   }
 *
 * Historical executions persist parameters as JSON, so numeric and boolean
 * values sometimes come back as strings (e.g. "true", "1.5").  The helpers
 * below normalise values before comparison so both live form state and
 * snapshot payloads evaluate the same way.
 */

import type {
  ConfigProperty,
  DependsOnCondition,
  JsonPrimitive,
} from '../types/strategy';

/**
 * Normalise a value so it can be compared against a schema's
 * `values` array, which uses raw JSON primitives.
 */
export function normalizeComparableValue(value: unknown): JsonPrimitive {
  if (value === null || value === undefined) return null;
  if (typeof value === 'string') {
    const trimmed = value.trim();
    const lower = trimmed.toLowerCase();
    if (lower === 'true') return true;
    if (lower === 'false') return false;
    if (trimmed === '') return null;
    const asNumber = Number(trimmed);
    if (!Number.isNaN(asNumber)) return asNumber;
    return trimmed;
  }
  if (typeof value === 'number' || typeof value === 'boolean') {
    return value;
  }
  return String(value);
}

/** True when `currentValue` matches `expected` after normalisation. */
export function conditionMatchesValue(
  currentValue: unknown,
  expected: JsonPrimitive
): boolean {
  return normalizeComparableValue(currentValue) === expected;
}

/**
 * Resolve a dependency field's current value, falling back to the
 * schema's declared default.  This matters for snapshot views: older
 * executions may not carry newer fields at all, but the effective
 * default still determines visibility.
 */
function resolveDependencyValue(
  params: Record<string, unknown>,
  schemaProperties: Record<string, ConfigProperty> | undefined,
  field: string
): unknown {
  if (field in params) return params[field];
  return schemaProperties?.[field]?.default;
}

/**
 * Evaluate a `dependsOn` block against `params` using the provided
 * schema for default fall-backs.  Returns `true` when the condition
 * is absent or satisfied.
 */
export function matchesDependsOn(
  params: Record<string, unknown>,
  dependsOn: DependsOnCondition | undefined,
  schemaProperties?: Record<string, ConfigProperty>
): boolean {
  if (!dependsOn) return true;

  const matchesSingleCondition = (cond: DependsOnCondition): boolean => {
    const raw = resolveDependencyValue(params, schemaProperties, cond.field);
    if (!cond.values.some((expected) => conditionMatchesValue(raw, expected))) {
      return false;
    }
    if (!cond.and || cond.and.length === 0) return true;
    return cond.and.every((andCond) => {
      const rawCond = resolveDependencyValue(
        params,
        schemaProperties,
        andCond.field
      );
      return andCond.values.some((expected) =>
        conditionMatchesValue(rawCond, expected)
      );
    });
  };

  if (matchesSingleCondition(dependsOn)) return true;
  if (!dependsOn.or || dependsOn.or.length === 0) return false;
  return dependsOn.or.some((orCond) => matchesSingleCondition(orCond));
}

/**
 * True when a parameter should be shown — i.e. it has no `dependsOn`
 * block, or all conditions evaluate to true against `params`.
 */
export function isParameterVisible(
  key: string,
  params: Record<string, unknown>,
  schemaProperties: Record<string, ConfigProperty> | undefined
): boolean {
  const prop = schemaProperties?.[key];
  if (!prop?.dependsOn) return true;
  return matchesDependsOn(params, prop.dependsOn, schemaProperties);
}
