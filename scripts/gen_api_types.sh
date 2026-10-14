#!/usr/bin/env sh
# Regenerate docs/openapi.json from the backend, then the frontend TypeScript types.
set -e
cd "$(dirname "$0")/.."
uv run python scripts/export_openapi.py
cd frontend && npm run gen:api
