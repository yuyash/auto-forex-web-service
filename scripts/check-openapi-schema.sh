#!/usr/bin/env bash
set -euo pipefail

cd backend
source .venv/bin/activate

tmpfile=$(mktemp)
trap 'rm -f "$tmpfile"' EXIT

python manage.py spectacular --file "$tmpfile" --format openapi-json --validate --fail-on-warn

# Ensure trailing newline (--file output lacks one; end-of-file-fixer adds one)
if [ -s "$tmpfile" ] && [ "$(tail -c 1 "$tmpfile" | wc -l)" -eq 0 ]; then
    printf '\n' >> "$tmpfile"
fi

if ! diff -q "$tmpfile" ../docs/openapi.json > /dev/null 2>&1; then
    echo "ERROR: docs/openapi.json is out of date."
    echo "Run:   bash scripts/generate-openapi-schema.sh"
    exit 1
fi
