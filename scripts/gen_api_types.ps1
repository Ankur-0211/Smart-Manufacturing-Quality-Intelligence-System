# Regenerate docs/openapi.json from the backend, then the frontend TypeScript types.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
uv run python scripts/export_openapi.py
Set-Location frontend
npm run gen:api
