#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

remote_base=""
if git rev-parse --verify --quiet "@{upstream}" >/dev/null; then
  remote_base="@{upstream}"
elif git rev-parse --verify --quiet origin/main >/dev/null; then
  remote_base="origin/main"
else
  remote_base="$(git rev-list --max-parents=0 HEAD | tail -n 1)"
fi

changed_files="$(git diff --name-only "${remote_base}...HEAD")"

if [[ -z "$changed_files" ]]; then
  echo "No pushed file changes detected; skipping scoped pre-push checks."
  exit 0
fi

run_backend=0
run_frontend=0

while IFS= read -r path; do
  [[ -z "$path" ]] && continue

  case "$path" in
    backend/*|docs/openapi.json)
      run_backend=1
      ;;
    frontend/*)
      run_frontend=1
      ;;
    .github/*|nginx/*|docker-compose*.yaml|docker-compose*.yml|Dockerfile|.pre-commit-config.yaml|AGENTS.md|DEVELOPMENT.md)
      run_backend=1
      run_frontend=1
      ;;
  esac
done <<< "$changed_files"

if [[ "$run_backend" -eq 0 && "$run_frontend" -eq 0 ]]; then
  echo "No backend or frontend-impacting pushed changes detected; skipping scoped pre-push checks."
  exit 0
fi

if [[ "$run_backend" -eq 1 ]]; then
  echo "Running backend pre-push checks..."
  (cd backend && source .venv/bin/activate && python scripts/ci_pytest.py prepush)
fi

if [[ "$run_frontend" -eq 1 ]]; then
  echo "Running frontend pre-push checks..."
  (cd frontend && npm run build)

  if grep -Eq '^(frontend/(package\.json|package-lock\.json|\.npmrc|Dockerfile))$' <<< "$changed_files"; then
    (cd frontend && npm ci --ignore-scripts --no-audit --no-fund)
  else
    echo "No frontend dependency metadata changed; skipping npm ci check."
  fi

  (cd frontend && npm run test)
fi
