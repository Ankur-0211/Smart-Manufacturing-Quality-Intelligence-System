# CCR-001: Add `ROUTE_NOT_FOUND` and `METHOD_NOT_ALLOWED` error codes

| Field | Value |
|---|---|
| Requested by | Role 2 |
| Date | 2026-10-15 |
| Status | proposed (implemented on `role-2-application`; needs Role 1 approval before merge to `main`) |
| Type | additive (MINOR) |

## Problem

Roadmap §9.3.4 lists no code for transport-level failures: a request to a path that does not
exist, or with an unsupported HTTP method. The error envelope always needs a stable `code`. None
of the existing codes fits:
- `REFERENCE_NOT_FOUND` and `RUN_NOT_FOUND` describe domain entities.
- `VALIDATION_ERROR` describes bad input.

## Proposed change

Add two codes:

| Code | HTTP | Meaning |
|---|---|---|
| `ROUTE_NOT_FOUND` | 404 | No API route matches the path |
| `METHOD_NOT_ALLOWED` | 405 | The route exists but not for this HTTP method |

## Affected

- `backend/app/api/errors.py` (enum + handler)
- `frontend/src/api/errors.ts` (mirrored union + message)
- Roadmap §9.3.4 code list (update on approval)

The intelligence interface, DB, events and fixtures are not affected.

## Compatibility

Purely additive. No existing code changes meaning.

## Tests updated

`backend/tests/api/test_errors.py::test_unknown_route_and_method`.

## Approvals

- Role 1 [ ]
- Role 2 [x]
