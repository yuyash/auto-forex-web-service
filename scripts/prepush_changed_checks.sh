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
  uv run --directory backend --extra dev python scripts/ci_pytest.py prepush
fi

frontend_npm_mode=""
frontend_deps_ready=0

frontend_npm() {
  if [[ -z "$frontend_npm_mode" ]]; then
    if command -v npm >/dev/null 2>&1; then
      frontend_npm_mode="npm"
    elif command -v npm.cmd >/dev/null 2>&1; then
      frontend_npm_mode="npm.cmd"
    elif command -v docker >/dev/null 2>&1; then
      frontend_npm_mode="docker"
      echo "npm not found; running frontend npm commands in Docker."
    else
      echo "npm is required for frontend pre-push checks but was not found." >&2
      return 127
    fi
  fi

  case "$frontend_npm_mode" in
    npm)
      (cd frontend && npm "$@")
      ;;
    npm.cmd)
      (cd frontend && npm.cmd "$@")
      ;;
    docker)
      docker_frontend_dir="$ROOT_DIR/frontend"
      if command -v cygpath >/dev/null 2>&1; then
        docker_frontend_dir="$(cygpath -m "$docker_frontend_dir")"
      fi
      MSYS_NO_PATHCONV=1 docker run --rm \
        -v "$docker_frontend_dir:/app" \
        -v auto_forex_frontend_node_modules:/app/node_modules \
        -w /app \
        node:24-alpine npm "$@"
      ;;
  esac
}

ensure_frontend_deps() {
  if [[ "$frontend_deps_ready" -eq 1 ]]; then
    return 0
  fi

  if grep -Eq '^(frontend/(package\.json|package-lock\.json|\.npmrc|Dockerfile))$' <<< "$changed_files"; then
    frontend_npm ci --ignore-scripts --no-audit --no-fund
    frontend_deps_ready=1
    return 0
  fi

  if [[ "$frontend_npm_mode" == "docker" || ! -d frontend/node_modules ]]; then
    echo "Frontend dependencies are missing; running npm ci."
    frontend_npm ci --ignore-scripts --no-audit --no-fund
    frontend_deps_ready=1
    return 0
  fi

  echo "No frontend dependency metadata changed; skipping npm ci check."
}

if [[ "$run_frontend" -eq 1 ]]; then
  echo "Running frontend pre-push checks..."
  frontend_npm --version >/dev/null
  ensure_frontend_deps
  frontend_npm run build
  frontend_npm run test
fi
