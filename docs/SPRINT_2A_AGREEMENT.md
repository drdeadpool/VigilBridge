# Sprint 2A Engineering Dashboard — Agreement Engine v0.1

**Date:** 2026-06-26
**Sprint:** Agreement Engine
**Commit:** TBD (pending push)
**Prior commit:** 4852fad (Validation Engine v0.1)
**Status:** Complete — pending push to main

---

## Deliverable Status

| # | Task | Status | Evidence |
|---|---|---|---|
| 1 | Agreement Service — pure SQL analytics over validation_records | ✅ Done | `app/services/agreement_service.py` |
| 2 | Agreement API — 2 read-only endpoints | ✅ Done | `app/api/v1/agreement.py` |
| 3 | Wire router in main.py | ✅ Done | `app/main.py` |
| 4 | Tests — 25 new tests (service + API) | ✅ Done | `tests/test_agreement_service.py` (15), `test_agreement_api.py` (12) |
| 5 | Engineering dashboard | ✅ Done | This document |

---

## Test Results

```
146 passed, 1 warning, 8 subtests passed in 0.93s   (Python 3.14, pytest 9.1.1)

Prior suite (121):
  AuthTest                          4/4
  BaselineServiceTest              14/14
  BaselinesApiTest                  5/5
  ConstraintEngineTest             16/16
  ExtractorActiveEnergyTest         5/5
  ExtractorRestingHrTest            9/9
  StateServiceTest                 10/10
  TrendServiceTest                 12/12
  TrendsApiTest                     5/5
  TrendsGateTest                    9/9
  ValidationApiTest                16/16
  ValidationServiceTest            11/11

New (Sprint 2A, 25 tests):
  AgreementApiTest                 12/12   PASS
  AgreementServiceTest             13/13   PASS (incl. key-count, rate semantics, null safety)
```

---

## Architecture

### Agreement Engine position in data flow

```
Postgres: validation_records  (written by Validation Engine v0.1)
                │
                ▼  (read-only SQL aggregations)
    agreement_service.get_summary()       → 17-key summary dict
    agreement_service.get_by_state()      → per-state breakdown list
                │
                ▼
    GET /agreement/{user_id}              [READ_API_KEY]
    GET /agreement/{user_id}/by-state     [READ_API_KEY]
```

No writes. No inference. No joins to other tables.

### Metrics schema

**Summary endpoint** (`GET /agreement/{user_id}?days=30`):

| Field | Definition | Type |
|---|---|---|
| `total` | COUNT(*) in period | int |
| `assessed` | confirmed + rejected + needs_review | int |
| `confirmed` | COUNT WHERE status='confirmed' | int |
| `rejected` | COUNT WHERE status='rejected' | int |
| `needs_review` | COUNT WHERE status='needs_review' | int |
| `pending` | COUNT WHERE status='pending' | int |
| `agreement_rate` | confirmed / assessed | float \| null |
| `disagreement_rate` | rejected / assessed | float \| null |
| `pending_rate` | pending / total | float \| null |
| `coverage` | assessed / total | float \| null |
| `mean_confidence` | AVG(confidence) | float \| null |
| `min_confidence` | MIN(confidence) | float \| null |
| `max_confidence` | MAX(confidence) | float \| null |
| `confidence_distribution` | bucketed histogram (4 bands) | dict[str, int] |
| `inference_by_version` | {engine_version: count} | dict[str, int] |

Rates are `null` when denominator is zero — distinguishes "no data" from 0% agreement.

**Confidence buckets:** `[0.0, 0.25)`, `[0.25, 0.5)`, `[0.5, 0.75)`, `[0.75, 1.0]`

**By-state endpoint** (`GET /agreement/{user_id}/by-state?days=30`):

Each entry in `by_state[]`: `inferred_state`, `total`, `confirmed`, `rejected`,
`needs_review`, `pending`, `agreement_rate`, `disagreement_rate`. Ordered by total desc.

---

## Implementation Notes

- Both service functions issue a single SQL query each (no N+1).
- Confidence distribution uses PostgreSQL `FILTER` aggregation — no application-side bucketing.
- `agreement_rate` and `disagreement_rate` intentionally do not sum to 1.0: `needs_review` records are assessed but neither confirmed nor rejected, so the gap is intentional and meaningful.
- Both endpoints reject ingest keys (401). Read key required.
- Days parameter: default 30, range 1–365.

---

## Cumulative Sprint 2/2A Deliverables

| Component | What shipped |
|---|---|
| `app/version.py` | Version constants (ENGINE=0.1, CONSTRAINT=0.1, EVIDENCE_MODEL=0.1) |
| `models/validation_record.py` | ValidationRecord ORM — UNIQUE(user_id, day), JSONB evidence |
| `alembic/a9f4e2d1b6c8` | validation_records migration — down_revision f2b3c8d5a1e9 |
| `services/validation_service.py` | create_or_update, get_record, get_history, update_operator |
| `api/v1/validation.py` | POST/GET/PATCH validation endpoints |
| `services/agreement_service.py` | get_summary, get_by_state — pure SQL analytics |
| `api/v1/agreement.py` | GET /agreement/{user_id}, GET /agreement/{user_id}/by-state |
| Tests | 146/146 passing (121 prior + 25 new) |

---

## Constraints Respected

- Human State Engine v0.1 FROZEN — `infer_state()` and `evaluate_constraints()` untouched.
- Validation persistence FROZEN — validation_service unchanged.
- No ML, no LLM, no prediction, no personalization.
- No new DB migrations (Agreement Engine is read-only).
- No UI.

---

## Sprint 2B Suggestions

### High priority

1. **Push 4852fad + current commit → prod** — Render auto-deploys, migration a9f4e2d1b6c8 applies, validation + agreement go live.
2. **Seed operator assessments** — Until validation records have operator assessments, all agreement rates will be null. First real validation event needed to verify end-to-end.

### Medium priority

3. **Agreement over time** — Add `GET /agreement/{user_id}/history?days=90&bucket=week` returning agreement_rate per time bucket. Enables "is operator agreement improving?" tracking.
4. **Cross-user aggregate** — Admin-scoped endpoint for fleet-wide agreement rate. Requires new auth scope.
5. **Confidence drift alert** — Flag when mean_confidence drops >0.1 vs. prior 7-day window. Signals data quality regression.
