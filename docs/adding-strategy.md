# Adding a Strategy

Use this checklist when adding a strategy that is not Snowball-shaped.

## Required Backend Pieces

1. Create `backend/apps/trading/strategies/<id>/strategy.py`.
2. Decorate the strategy class with `@register_strategy(id="<id>", schema="trading/schemas/<id>.json")`.
3. Implement `parse_config`, `default_parameters`, and `validate_parameters` if the base JSON schema validation is not enough.
4. Add `backend/apps/trading/schemas/<id>.json` with all UI metadata needed by the frontend.

`backend/apps/trading/strategies/custom/` is the minimal no-op skeleton. Copy it
when starting a strategy that should not inherit Snowball behavior.

## Optional Strategy Hooks

Override these hooks only when the strategy owns that behavior:

- `capabilities()` exposes runtime, visualization, event, and resume support to generic services and the frontend. Hedging is opt-in: leave `runtime.hedging` false unless the strategy can safely hold simultaneous long and short positions.
- `configure_runtime()` receives task/account options such as account currency and hedging.
- `build_cycle_status_map()` maps persisted strategy state to cycle statuses.
- `build_cycle_grid_state_map()` maps persisted strategy state to grid visualization data.
- `supports_stateful_broker_reconciliation()` and `reconcile_broker_positions()` opt into state-aware resume reconciliation.
- `validate_resume_parameter_compatibility()` blocks parameter changes that cannot safely resume against persisted state.

Generic services must call these hooks through the registry rather than importing a concrete strategy package.

## Frontend Expectations

The frontend should read behavior from strategy schema and capabilities:

- Use schema properties for fields, groups, labels, enum labels, enum descriptions, visibility, and hidden enum values.
- Use `capabilities.runtime.hedging` before showing hedging controls.
- Use `capabilities.visualization.kind` and related flags before rendering strategy-specific visualization.
- Treat strategy event IDs and close reasons as opaque values unless labels are supplied by strategy capabilities.

## Tests

Add or update tests that prove:

- The strategy registers through discovery.
- Parameters validate through the registry.
- Generic services return empty/default behavior for strategies without optional hooks.
- Any strategy-specific visualization, reconciliation, or resume compatibility behavior lives under that strategy package.
