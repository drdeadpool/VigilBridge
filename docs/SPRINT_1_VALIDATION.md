# Sprint 1 Engineering Validation

**Date:** 2026-06-26  
**Sprint:** Human State Engine v0.1  
**Commit:** d2cd36c  
**Status:** Complete — pending push to main

---

## Deliverable Status

| # | Task | Status | Evidence |
|---|---|---|---|
| 1 | Alembic migration: `constraints` + `state_estimates` | ✅ Done | `f2b3c8d5a1e9_create_state_engine_tables.py` |
| 2 | SQLAlchemy models: Constraint, StateEstimate | ✅ Done | `app/models/constraint.py`, `state_estimate.py` |
| 3 | Constraint Engine v0.1 — 6 deterministic rules | ✅ Done | `app/services/constraint_engine.py` |
| 4 | Human State Estimator v0.1 — priority cascade | ✅ Done | `app/services/state_service.py` |
| 5 | API: GET/POST state endpoints + wire in main.py | ✅ Done | `app/api/v1/state.py`, `app/main.py` |
| 6 | Ingest hook — state recompute after POST /ingest | ✅ Done | `app/api/v1/ingest.py` |
| 7 | Tests: 26 unit tests, 26/26 passing | ✅ Done | `tests/test_constraint_engine.py` (16), `test_state_service.py` (10) |
| 8 | Active energy: permission + code audit | ✅ Done | See Task 2 finding below |
| 9 | ADR-005: Recovery Inference | ✅ Done | `docs/adr/ADR-005-recovery-inference.md` |

---

## Test Results

```
26 passed in 0.69s   (Python 3.14, pytest 9.1.1)

ConfidenceTest                         4/4   PASS
RuleEvaluatorTest                      8/8   PASS  (includes 2 no-fire guards, zero-std guard)
EvaluateAllConstraintsTest             4/4   PASS
StateSpaceTest                         1/1   PASS  (vocabulary frozen)
InsufficientEvidenceTest               2/2   PASS
RecoveryDeficitTest                    1/1   PASS
StrainOvershootTest                    2/2   PASS  (includes long-sleep compensation block)
ActiveRecoveryTest                     1/1   PASS
NormalTest                             1/1   PASS
PriorityTest                           1/1   PASS  (recovery outranks strain)
EvidenceRefsTest                       1/1   PASS  (JSONB shape)
```

---

## Implementation Graph

```
Android (S24 Ultra)
├─ HealthRepository.load()
│   ├─ aggregateSteps (today/7d/30d)
│   ├─ readLastSleep → SleepMerger → actualSleepMinutes
│   ├─ readRestingHR → RestingHeartRateRecord ∅ → HeartRateRecord.BPM_MIN fallback
│   └─ aggregateActiveEnergy → ActiveCaloriesBurnedRecord ∅ (OEM silo, see blocker B1)
└─ SnapshotCaptureStore → outbox → OutboxUploadWorker
    └─ POST /ingest  [INGEST_API_KEY]
        │
        ▼ backend/app/api/v1/ingest.py
        ├─ extractor._extract_vigil_snapshot()
        │   └─ → observations (Postgres, 7+ metric types)
        ├─ baseline_service.compute_and_store_baselines()
        │   └─ → baselines (Postgres, mean/std/n per metric × period)
        └─ state_service.compute_and_store_state()  ← NEW Sprint 1
            ├─ constraint_engine.compute_and_store_constraints()
            │   ├─ _fetch_daily_stats() → (valid_days, mean, std per metric)
            │   ├─ _fetch_today_values() → today's daily-reduced values
            │   ├─ evaluate_constraints() → 6 rules × (fires, severity, confidence, evidence)
            │   └─ → constraints (Postgres, upsert per user/day/name)
            ├─ infer_state() → priority cascade → (state, confidence, rationale)
            ├─ build_evidence_refs() → JSONB provenance
            └─ → state_estimates (Postgres, upsert per user/day)

Read API:
    GET  /state/{user_id}         → compute_and_store_state()  [READ_API_KEY]
    GET  /state/{user_id}/history → state_estimates last 14d   [READ_API_KEY]
    POST /state/{user_id}/recompute → compute_and_store_state() [READ_API_KEY]
```

---

## Task 2: Active Energy Verification

**Verdict:** Code correct on all layers. OEM blocker.

| Layer | Status |
|---|---|
| `READ_ACTIVE_CALORIES_BURNED` in manifest | ✅ Present |
| Permission granted on device R5CXB2KE0VF | ✅ granted=true |
| `aggregateActiveEnergy()` in HealthRepository | ✅ Correct — uses `ActiveCaloriesBurnedRecord.ACTIVE_CALORIES_TOTAL` |
| `activeEnergyKcal` in RawDashboard + VigilApiClient payload | ✅ Wired |
| `active_energy` extraction in extractor.py | ✅ Present (commit cd39e95) |
| Active energy arriving in prod observations | ❌ **Never** — Samsung Health does not write `ActiveCaloriesBurnedRecord` to HC on S24 Ultra |

**Same OEM siloing pattern as BUG-006 (RestingHeartRateRecord).** No code change needed. Will resolve if Samsung Health adds HC write support for this record type.

---

## Blockers

| ID | Blocker | Impact | Resolution path |
|---|---|---|---|
| B1 | Samsung Health does not write `ActiveCaloriesBurnedRecord` to Health Connect on S24 Ultra | `active_energy` absent from all payloads; `active_recovery` state can't use energy signal | OEM change needed; no workaround available |
| B2 | Commit d2cd36c not pushed to main | Human State Engine not live on prod Render | `git push origin main` — triggers auto-deploy |
| B3 | `resting_hr_bpm` absent on days with no sleep in 02:00–06:00 window | Constraint `rhr_elevated`/`rhr_suppressed` can't fire → state defaults to `data_gap` or `normal` incorrectly | No fix available within current sensor set; document as known limitation in ADR-005 |
| B4 | BUG-009: sleep dated by local sleep-start, no physiological-night anchor | Occasional duplicate sleep date (Jun 20 ×2 / Jun 21 ×0) propagates into `sleep_duration_hours` baseline | Address in Phase 3 Circadian Engine (already deferred) |

---

## Sprint 2 Suggestions

### High priority (unblocked, high value)

1. **Push d2cd36c → deploy** — Human State Engine goes live in prod. State table starts populating on next ingest.
2. **Trend × State integration** — Trend Engine v1 already produces `direction_of_good` per metric. Wire trend slope direction into state context (`trend_refs` JSONB in `state_estimates`). Enables detecting "normal today but declining 7-day trend."
3. **BUG-009 fix (sleep anchor)** — Anchor `sleep_duration_hours` to physiological night (bedtime local date) rather than sleep-start local date. Prerequisite for reliable `sleep_short`/`sleep_long` constraint firing.

### Medium priority (meaningful signal expansion)

4. **`active_recovery` HRV gate** — If HRV data becomes available via HC (requires future device/app support), add as a modifier to the `active_recovery` → `recovery_deficit` discriminator.
5. **Consecutive-day state sequences** — `state_estimates` table already present. Add `GET /state/{user_id}/streak` endpoint returning current run length per state. Clinical value: 3 consecutive `recovery_deficit` is more actionable than 1.
6. **State confidence display in Android dashboard** — `DashboardUiState` currently shows only biometric values. Add inferred state + confidence from `GET /state/{user_id}`.

### Low priority / deferred

7. **Severity-weighted cascade** — Replace first-match priority with `sum(severity × confidence)` across constraint groups. Requires ADR update and test expansion. Not warranted until ≥5 metrics in scope.
8. **BUG-010 sleep card UX** — Show time-in-bed alongside actual sleep in dashboard. Data already in Postgres; pure UI change.

---

## Sprint 1 Summary

Sprint 1 built the Human State Engine from scratch (all prior work was planned-only). Delivered in one session:

- **2 new DB tables** with JSONB evidence columns
- **2 new services** (Constraint Engine + State Estimator), purely functional, zero DB coupling in hot path
- **3 new API endpoints**
- **26 unit tests, 26/26 passing**
- **Ingest hook** — state stays fresh without manual recompute
- **ADR-005** grounded in actual implementation

The only Sprint 1 task requiring unplanned investigation was active energy (Task 2): the Android permission and code were already correct; the blocker is Samsung Health data siloing confirmed on-device.

**Sprint 1 is complete. d2cd36c is ready to push.**
