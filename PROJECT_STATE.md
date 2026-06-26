# VigilBridge — Project State

Last updated: 2026-06-26. Written for zero-context continuation.

---

## Current Phase

**Scientific Operations — ACTIVE** (Engineering Foundation FROZEN)

The Engineering Foundation is complete as of Sprint 3 (commit 2182269). All production systems deployed, verified, and frozen. Work mode has transitioned from implementation to operation: collect validation records, record operator assessments, measure agreement, build longitudinal evidence.

**No new engineering work until operational evidence justifies it.**

---

## Production Status

| Component | Status | Evidence |
|---|---|---|
| Backend API | Live | vigilbridge.onrender.com, Render free tier |
| Database | Live | Postgres, 1126 observations, 1 user |
| Alembic migrations | Applied | 7 migrations, head: `a9f4e2d1b6c8` |
| Tests | 146/146 passing | Python 3.14.5, pytest 9.1.1 |
| Android app | Deployed | Debug APK, R5CXB2KE0VF, WorkManager proven |
| Pipeline | Firing | Android → ingest → baselines → constraints → state → validation |

### Latest production stats (2026-06-26)

```json
{
  "total_observations": 1126,
  "observation_types": {
    "steps_30d": 364, "steps_7d": 364, "steps_today": 305,
    "sleep_sessions_count": 16, "sleep_duration_hours": 16,
    "sleep_start_hour": 16, "sleep_end_hour": 16, "time_in_bed_hours": 16,
    "resting_hr_bpm": 9, "unknown": 4
  },
  "latest_timestamp": "2026-06-26T09:43Z"
}
```

---

## Frozen Systems (v1.0)

| System | Version | Frozen Since | Key Files |
|---|---|---|---|
| Observation Schema | v1.0 | Sprint 3 | `models/observation.py`, migration `77f7b348bccf` |
| Evidence Model | v1.0 | Sprint 3 | `models/constraint.py`, `models/state_estimate.py` |
| Baseline Engine | v1.0 | Sprint 3 | `services/baseline_service.py` |
| Trend Engine | v1.0 | Sprint 3 | `services/trend_service.py`, `api/v1/trends.py` |
| Constraint Engine | v1.0 | Sprint 1 | `services/constraint_engine.py` |
| Human State Engine | v1.0 | Sprint 1 | `services/state_service.py` |
| Validation Engine | v1.0 | Sprint 2 | `services/validation_service.py`, `api/v1/validation.py` |
| Agreement Engine | v1.0 | Sprint 2A | `services/agreement_service.py`, `api/v1/agreement.py` |
| Persistence Model | v1.0 | Sprint 3 | 7 migrations, 7 tables |
| API | v1.0 | Sprint 3 | `api/v1/`, 16 endpoints |

Changes require operational evidence. No exceptions without an ADR.

---

## API Endpoints (16 total)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | /health | None | Liveness + DB check |
| POST | /ingest | INGEST_API_KEY | Receive HC snapshot from device |
| GET | /stats | READ_API_KEY | Observation counts and types |
| GET | /observations/recent | READ_API_KEY | Recent valid observations |
| GET | /baselines/{user_id} | READ_API_KEY | Current baselines |
| POST | /baselines/{user_id}/recompute | READ_API_KEY | Force baseline recompute |
| GET | /trends/{user_id}/{metric} | READ_API_KEY | Per-metric trend data |
| GET | /state/{user_id} | READ_API_KEY | Current inferred human state |
| GET | /state/{user_id}/history | READ_API_KEY | State history (default 14d) |
| POST | /state/{user_id}/recompute | READ_API_KEY | Force state recompute |
| POST | /validation | INGEST_API_KEY | Create/update validation record |
| GET | /validation | READ_API_KEY | List validation records |
| GET | /validation/{id} | READ_API_KEY | Single validation record |
| PATCH | /validation/{id} | READ_API_KEY | Update operator assessment |
| GET | /agreement/{user_id} | READ_API_KEY | Agreement analytics summary |
| GET | /agreement/{user_id}/by-state | READ_API_KEY | Per-state agreement breakdown |

---

## Database Tables (7)

| Table | Rows (approx) | Purpose |
|---|---|---|
| users | 4 (1 active canonical, 3 legacy/test) | User registry (external_id → UUID) |
| devices | 1 | Device registry |
| observations | 1126 | Raw biometric measurements |
| baselines | ~3–9 | Per-metric mean/std/n per period |
| constraints | ~6/day | Daily constraint evaluation results |
| state_estimates | ~1/day | Daily inferred human state |
| validation_records | ~1/day | Versioned inference snapshots + operator assessment |

---

## Human State Engine

**States (frozen):** `data_gap`, `recovery_deficit`, `strain_overshoot`, `active_recovery`, `normal`

**BASELINE_METRICS:** `sleep_duration_hours`, `resting_hr_bpm`, `steps_today`

**MIN_VALID_DAYS=3** (below threshold → `data_gap`)

**FULL_CONFIDENCE_DAYS=14** (confidence = min(1.0, valid_days/14))

**Constraint rules (6):** `sleep_short`, `sleep_long`, `steps_low`, `steps_high`, `rhr_elevated`, `rhr_suppressed`

Firing threshold: |z| ≥ 1 SD from personal baseline.

**Priority cascade (first match wins):**
1. `data_gap` — valid_days < 3 OR any BASELINE_METRIC absent today
2. `recovery_deficit` — sleep_short AND rhr_elevated
3. `strain_overshoot` — steps_high AND rhr_elevated AND NOT sleep_long
4. `active_recovery` — steps_low AND sleep_long
5. `normal` — otherwise

---

## Validation System

**Status vocabulary:** `pending`, `confirmed`, `rejected`, `needs_review`

**Version tags (all records):** `engine_version=0.1`, `constraint_version=0.1`, `evidence_model_version=0.1`

**Agreement metrics available (all null until operator assessments exist):**
- agreement_rate, disagreement_rate, pending_rate
- confidence_distribution (4 buckets)
- inference_by_version
- agreement_by_state (per-state breakdown)

---

## Android App — Working Features

| Feature | Status |
|---|---|
| Health Connect integration | ✅ Working |
| Steps (today/7d/30d) | ✅ Working |
| Sleep duration (SleepMerger) | ✅ Working |
| Resting HR (BPM_MIN fallback) | ✅ Working |
| Background sync (WorkManager, 15-min) | ✅ Proven |
| Outbox with retry | ✅ Working |
| POST /ingest with INGEST_API_KEY | ✅ Working |

---

## Known Open Bugs

| ID | Severity | Status | Description |
|---|---|---|---|
| BUG-003 | Low | Open | UnavailableScreen magic int literals |
| BUG-005 | Low | Open | collectAsState vs collectAsStateWithLifecycle |
| BUG-007 | Cosmetic | Open | versionName = "1.0" should reflect actual version |
| BUG-009 | Medium | Deferred | Sleep dated by sleep-start, no physiological-night anchor → occasional day miscounting |
| BUG-010 | Low | Deferred | Dashboard shows actual sleep only, not time-in-bed |

---

## Key ADRs

| ADR | Status | Decision |
|---|---|---|
| ADR-005 | Accepted | Deterministic priority cascade for Human State inference (not ML, not scoring) |

---

## Immediate Operational Priorities

1. Verify production daily — `curl https://vigilbridge.onrender.com/health`
2. Run Human State Engine continuously (fires automatically on each ingest)
3. Collect validation records (automatic)
4. Record operator assessments via PATCH /validation/{id}
5. Review agreement metrics via GET /agreement/{user_id}
6. Build ≥30 days of operator-assessed records before any engineering review

---

## Session Start Protocol

1. Read CLAUDE.md (authoritative guide)
2. Read PROJECT_STATE.md (this file)
3. Verify backend health: `curl https://vigilbridge.onrender.com/health`
4. Check DB state: `curl https://vigilbridge.onrender.com/stats -H "X-Api-Key: <READ_API_KEY>"`
5. Check device: `adb -s R5CXB2KE0VF devices`
6. **Ask: what operational evidence justifies this task?**

---

## Device / Infrastructure Reference

| Item | Value |
|---|---|
| Device | Samsung Galaxy S24 Ultra |
| Device serial | R5CXB2KE0VF |
| Android ID (external_id) | aad1d7da558d58f2 |
| User UUID | 37c5d374-d624-404f-ae6f-50a6781601bf |
| ADB path | C:\Users\kaliv\AppData\Local\Android\Sdk\platform-tools\adb.exe |
| Backend URL | https://vigilbridge.onrender.com |
| Render tier | Free (cold start ~30s after idle) |
| GitHub | drdeadpool/VigilBridge, auto-deploy from main |
| Last commit | 2182269 |
| Migration head | a9f4e2d1b6c8 (create_validation_records) |
