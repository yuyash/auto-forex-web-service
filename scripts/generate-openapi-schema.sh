#!/usr/bin/env bash
set -euo pipefail

cd backend
uv run python manage.py spectacular --file ../docs/openapi.json --format openapi-json

# Ensure trailing newline to satisfy end-of-file-fixer
if [ -s ../docs/openapi.json ] && [ "$(tail -c 1 ../docs/openapi.json | wc -l)" -eq 0 ]; then
    printf '\n' >> ../docs/openapi.json
fi

echo "docs/openapi.json updated."
