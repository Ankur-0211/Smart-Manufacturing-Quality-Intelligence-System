# CCR-003: Review notes on contracts part 1 (Role 1)

| Field | Value |
|---|---|
| Requested by | Role 2 |
| Date | 2026-10-16 |
| Status | proposed (questions for Role 1; Role 2 has **not** edited any part-1 file) |
| Type | clarification + formatting; possibly MINOR |

Part 1 was received on 2026-10-16 and committed unchanged: `version.py`, `enums.py`, `recipe.py`,
`context.py` and `errors.py`. It matches roadmap §7.2–§7.7 and §9.1. All five Role 1 recipe
fixtures validate against `ProcessInput`. The files pass `mypy --strict`.

## Findings

1. **`ProcessInput.flat()` key set (§7.7).** The roadmap says the flat dict has "all raw fields, with
   `machine_id`, `product_id`, `resin_grade` as categoricals … minus identity, target and diagnostic
   columns". The current `flat()` returns 41 keys. Two of them may not belong:
   - `material_lot_id` is an identity code, which §7.7 says to drop. Training on a lot id would
     leak lot identity into the model.
   - `machine_type` is a categorical that §7.7 doesn't list.

   **Question:** should `flat()` exclude `material_lot_id`? Should `machine_type` be added to the
   categorical list in §7.7, or left out of `flat()`? Role 2 doesn't call `flat()` today, so either
   answer is fine for us.
2. **Missing files.** `backend/app/contracts/__init__.py` and
   `backend/tests/contract/test_contracts_part1.py` weren't in the upload.
   - Role 2 added a one-line `__init__.py` docstring so the package type-checks.
   - Role 1 should send the part-1 test file.
3. **Formatting.** None of the five files ends with a newline, and `ruff format` would rewrap
   `_RISK_ORDER` and the `IntelligenceError.__init__` signature. Until Role 1 runs
   `uv run ruff format backend/app/contracts`, `pyproject.toml` carries a temporary per-file
   exclusion, marked `CCR-003`.
4. **`IntelligenceError` signature.** §9.1 writes `IntelligenceError(code, message, …)`. Part 1
   instead uses a class-level `code` and `__init__(message, field, hint, details)`. Role 2 is fine
   with part 1's form, since it reads `.code`. **Proposal:** update the §9.1 wording to match.

## Role 2 changes made on receipt

- `app/db/vocab.py` now reads its values from `app.contracts.enums` and `app.contracts.recipe`
  instead of a transcription. `tests/db/test_vocab_matches_contracts.py` now checks the contracts
  against the values frozen in migration 0001.
- The contract harness imports `ProcessInput` from `app.contracts.context`. Part 1 places it there,
  as §7.7 says.
- mypy strict now covers `backend/app/contracts`.
