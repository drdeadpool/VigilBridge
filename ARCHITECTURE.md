# Vigil — Architecture

Last updated: 2026-06-26. Reflects v1.0 frozen state.

---

## System Overview

```
Samsung Galaxy S24 Ultra
  └─ Samsung Health (writes biometrics to Health Connect)
       └─ Health Connect (on-device health data store)
            └─ VigilBridge Android App
                 ├─ Foreground: HealthRepository reads HC → Dashboard UI
                 ├─ Background: WorkManager (15-min) reads HC → Room + Outbox
                 └─ Network: OutboxUploadWorker POSTs snapshot → vigilbridge.onrender.com
                                                                          │
                              FastAPI + uvicorn (Render free tier) ◄──────┘
                                    │
                              POST /ingest
                                    │
                              extract_observations()
                                    │
                              PostgreSQL 16 (Render managed)
                                    │
                    ┌───────────────┼───────────────────┐
                    ▼               ▼                   ▼
             observations      baselines          constraints
                                    │                   │
                                    └───────────────────┘
                                              │
                                     state_estimates
                                              │
                                    validation_records
                                              │
                                   Agreement Analytics
                                   (read-only SQL layer)
                                              │
                                  [Future: Insight Engine]
                                  [Future: Circadian Engine]
                                  [Future: Recovery Engine]
                                  [Future: Intelligence Layer]
```

---

## Backend Pipeline (per ingest)

```
POST /ingest [INGEST_API_KEY]
  │
  ├─ Upsert User (by external_id)
  ├─ Upsert Device (by user_id + device_identifier)
  ├─ extract_observations(payload)
  │    └─ INSERT INTO observations (ON CONFLICT DO UPDATE)
  ├─ COMMIT
  │
  ├─ [if BASELINE_METRICS present]
  │    ├─ recompute_baselines_for(user_id)
  │    │    └─ UPSERT INTO baselines (mean/std/n per metric × period)
  │    │
  │    └─ compute_and_store_state(user_id)
  │         ├─ compute_and_store_constraints(user_id, day)
  │         │    └─ UPSERT INTO constraints (6 rules, evidence JSONB)
  │         ├─ infer_state(constraints) → state, confidence, evidence_refs
  │         ├─ UPSERT INTO state_estimates
  │         └─ [returns StateResult]
  │              └─ create_or_update(db, state_result)
  │                   └─ UPSERT INTO validation_records
  │                        (preserves operator_assessment on re-inference)
  │
  └─ 202 Accepted + {user_id, accepted, observations}
```

---

## Data Flow Layers

```
Layer 0 — Raw Sensor Data
  observations (user_id, metric_type, value, unit, timestamp, raw_payload JSONB)

Layer 1 — Statistical Baselines
  baselines (user_id, metric_type, period_days, mean, std, n, min_val, max_val)

Layer 2 — Constraint Evaluation
  constraints (user_id, day, name, fires, severity, confidence, evidence JSONB)
  6 rules: sleep_short, sleep_long, steps_low, steps_high, rhr_elevated, rhr_suppressed

Layer 3 — Human State Inference
  state_estimates (user_id, day, state, confidence, contributing_constraints JSONB, evidence_refs JSONB)
  5 states: data_gap, recovery_deficit, strain_overshoot, active_recovery, normal

Layer 4 — Validation + Operator Assessment
  validation_records (user_id, day, engine_version, constraint_version, evidence_model_version,
                      inferred_state, confidence, evidence_provenance JSONB,
                      validation_status, operator_assessment, validated_at)

Layer 5 — Agreement Analytics (read-only)
  agreement_service: get_summary(), get_by_state()
  No writes — pure SQL aggregation over validation_records

[Future Layer 6 — Insight Engine (read-only SQL analytics)]
[Future Layer 7 — Circadian Engine]
[Future Layer 8 — Recovery Engine]
[Future Layer 9 — Intelligence Layer (Claude API)]
```

---

## Evidence Provenance Chain

```
observation.raw_payload (JSONB)
    ↓ extract + daily reduce
constraint.evidence → {metric, direction, today, baseline_mean, baseline_std, z, valid_days}
    ↓ evaluate_constraints()
state_estimate.evidence_refs → {today_values, baselines_used, valid_days}
state_estimate.contributing_constraints → ["sleep_short", "rhr_elevated"]
    ↓ create_or_update()
validation_record.evidence_provenance → immutable snapshot of evidence_refs
validation_record.contributing_constraints → immutable snapshot
validation_record.engine_version / constraint_version / evidence_model_version
    ↓ operator review
validation_record.validation_status + operator_assessment + validated_at
    ↓ aggregate
agreement_service.get_summary() → rates, distributions, version counts
agreement_service.get_by_state() → per-state breakdown
```

---

## Database Schema (7 tables, 7 migrations)

### Migration Chain

```
77f7b348bccf  initial_schema                     → users, devices, observations
a3f92c1d4e87  add_unique_constraint_obs           → observations UNIQUE(user_id, metric_type, timestamp)
b7c4d1e8f2a9  add_observation_data_quality        → data_quality_status, quality_reason, reviewed_at
d9f3a7b2c5e1  create_baselines_table             → baselines
e1a2c4f9d3b7  anchor_resting_hr_physiological_day → observations resting_hr timestamp anchor
f2b3c8d5a1e9  create_state_engine_tables          → constraints, state_estimates   [Sprint 1]
a9f4e2d1b6c8  create_validation_records           → validation_records              [Sprint 2]
```

### Key tables

```sql
-- Users (external_id = Android Settings.Secure.ANDROID_ID)
users (id UUID PK, external_id VARCHAR UNIQUE, display_name, created_at, updated_at)

-- Observations (FHIR-mappable)
observations (
    id UUID PK, user_id UUID FK, device_id UUID FK,
    metric_type VARCHAR(128), value NUMERIC(12,4), unit VARCHAR(64),
    timestamp TIMESTAMPTZ,           -- event time, UNIQUE(user_id, metric_type, timestamp)
    source VARCHAR(128),
    raw_payload JSONB,               -- full original HC payload preserved
    data_quality_status VARCHAR(32), -- valid / probe / legacy / superseded
    quality_reason VARCHAR(255),
    reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ
)

-- Baselines (one current baseline per metric × period, upserted on recompute)
baselines (
    id UUID PK, user_id UUID FK,
    metric_type VARCHAR(64), period_days INTEGER,   -- UNIQUE(user_id, metric_type, period_days)
    n INTEGER, mean FLOAT, std FLOAT, min_val FLOAT, max_val FLOAT,
    computed_at TIMESTAMPTZ
)

-- Constraints (one row per rule per day, upserted on recompute)
constraints (
    id UUID PK, user_id UUID FK, day DATE,           -- UNIQUE(user_id, day, name)
    name VARCHAR(64), fires BOOLEAN, severity INTEGER,
    confidence FLOAT, evidence JSONB, computed_at TIMESTAMPTZ
)

-- State estimates (one row per day, upserted on recompute)
state_estimates (
    id UUID PK, user_id UUID FK, day DATE,           -- UNIQUE(user_id, day)
    state VARCHAR(64), confidence FLOAT,
    contributing_constraints JSONB, evidence_refs JSONB,
    rationale TEXT, computed_at TIMESTAMPTZ
)

-- Validation records (versioned, operator-assessable)
validation_records (
    id UUID PK, user_id UUID FK, day DATE,           -- UNIQUE(user_id, day)
    engine_version VARCHAR(16), constraint_version VARCHAR(16),
    evidence_model_version VARCHAR(16),
    inferred_state VARCHAR(64), confidence FLOAT,
    contributing_constraints JSONB, evidence_provenance JSONB,
    explanation TEXT,
    validation_status VARCHAR(32),  -- pending / confirmed / rejected / needs_review
    operator_assessment TEXT,       -- nullable; preserved on re-inference
    notes TEXT,
    inferred_at TIMESTAMPTZ, validated_at TIMESTAMPTZ, created_at TIMESTAMPTZ
)
```

---

## API Surface (16 endpoints)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | /health | None | Liveness + DB |
| POST | /ingest | INGEST_API_KEY | Receive HC snapshot |
| GET | /stats | READ_API_KEY | Observation counts |
| GET | /observations/recent | READ_API_KEY | Recent observations |
| GET | /baselines/{user_id} | READ_API_KEY | Current baselines |
| POST | /baselines/{user_id}/recompute | READ_API_KEY | Force recompute |
| GET | /trends/{user_id}/{metric} | READ_API_KEY | Trend series |
| GET | /state/{user_id} | READ_API_KEY | Current state |
| GET | /state/{user_id}/history | READ_API_KEY | State history |
| POST | /state/{user_id}/recompute | READ_API_KEY | Force state recompute |
| POST | /validation | INGEST_API_KEY | Create/update validation record |
| GET | /validation | READ_API_KEY | List records |
| GET | /validation/{id} | READ_API_KEY | Single record |
| PATCH | /validation/{id} | READ_API_KEY | Update operator assessment |
| GET | /agreement/{user_id} | READ_API_KEY | 17-key summary |
| GET | /agreement/{user_id}/by-state | READ_API_KEY | Per-state breakdown |

**Auth pattern:** `secrets.compare_digest` constant-time compare. INGEST_API_KEY write-only scope, READ_API_KEY read-only scope. Cross-access blocked.

---

## Human State Engine (FROZEN v1.0)

### BASELINE_METRICS

```python
BASELINE_METRICS = ("sleep_duration_hours", "resting_hr_bpm", "steps_today")
MIN_VALID_DAYS = 3
FULL_CONFIDENCE_DAYS = 14
```

### Constraint Engine (6 rules)

```
Firing condition: |z| >= 1 AND value on correct directional side
Confidence: min(1.0, valid_days / 14)

Rule             Metric                Direction
sleep_short      sleep_duration_hours  -1  (today < mean - 1SD)
sleep_long       sleep_duration_hours  +1  (today > mean + 1SD)
steps_low        steps_today           -1
steps_high       steps_today           +1
rhr_elevated     resting_hr_bpm        +1
rhr_suppressed   resting_hr_bpm        -1
```

### State Cascade (priority order, first match wins)

```
1. data_gap         valid_days < 3 OR any BASELINE_METRIC absent today
2. recovery_deficit sleep_short AND rhr_elevated
3. strain_overshoot steps_high AND rhr_elevated AND NOT sleep_long
4. active_recovery  steps_low AND sleep_long
5. normal           (otherwise)
```

---

## Android Architecture

### Data flow

```
User taps Refresh (or WorkManager fires)
  → HealthRepository.load()
      ├─ client.aggregate(steps today/7d/30d)
      ├─ SleepMerger: merges sessions within 30-min gaps, computes actual sleep from stages
      └─ readRestingHR():
           Stage 1: RestingHeartRateRecord.BPM_AVG (returns null on S24 Ultra — OEM siloing)
           Stage 2: HeartRateRecord.BPM_MIN over 02:00–06:00 device-local window
  → SnapshotCaptureStore: Room snapshot + immutable sync_outbox entry (one transaction)
  → OutboxUploadWorker [network-constrained, exponential retry]
      → POST https://vigilbridge.onrender.com/ingest
          → Response: {user_id, accepted, observations}
```

### Package structure

```
com.batman.vigilbridge/
├── MainActivity.kt           — HC init, permission launcher, WorkManager schedule
├── data/
│   ├── HealthRepository.kt   — All HC queries, SleepMerger, SnapshotCaptureStore
│   ├── SleepMerger.kt        — Merges split sessions, computes actual sleep from stages
│   ├── SnapshotCaptureStore.kt — Room write + outbox in one transaction
│   ├── VitalsSnapshot.kt     — Room entity
│   ├── VitalsDao.kt          — insert, getLatest, getRecent(n)
│   └── VigilDatabase.kt      — Room singleton
├── network/
│   └── VigilApiClient.kt     — OkHttp, POST /ingest, reads BuildConfig for keys
├── ui/
│   ├── DashboardScreen.kt    — All Composables
│   └── DashboardViewModel.kt — StateFlow<DashboardUiState>, refresh()
└── work/
    ├── VitalsSyncWorker.kt   — 15-min periodic CoroutineWorker
    └── OutboxUploadWorker.kt — Outbox drain, network-constrained
```

### Health Connect permissions (all 4 required)

| Permission | Purpose |
|---|---|
| health.READ_STEPS | Step count aggregates |
| health.READ_SLEEP | Sleep session records |
| health.READ_RESTING_HEART_RATE | Resting HR (returns null on S24 Ultra) |
| health.READ_HEART_RATE | HeartRate fallback for resting HR |
| health.READ_HEALTH_DATA_IN_BACKGROUND | WorkManager background reads |

---

## Backend Stack

| Component | Technology |
|---|---|
| API | FastAPI 0.115 |
| ASGI | uvicorn 0.34 |
| ORM | SQLAlchemy 2.0 async |
| Migrations | Alembic 1.15 |
| DB driver | asyncpg 0.30 |
| Validation | Pydantic v2 |
| Python | CPython 3.12 |
| Container | Docker slim |
| Deployment | Render free tier |
| Database | PostgreSQL 16 (Render managed) |

### Backend file structure

```
backend/
├── app/
│   ├── main.py              — FastAPI app, CORS, router registration
│   ├── config.py            — Settings (DATABASE_URL, INGEST_API_KEY, READ_API_KEY)
│   ├── database.py          — Async engine, session factory, Base
│   ├── auth.py              — require_ingest_key, require_read_key dependencies
│   ├── version.py           — ENGINE_VERSION, CONSTRAINT_VERSION, EVIDENCE_MODEL_VERSION
│   ├── models/
│   │   ├── user.py          — User
│   │   ├── device.py        — Device
│   │   ├── observation.py   — Observation
│   │   ├── baseline.py      — Baseline
│   │   ├── constraint.py    — Constraint
│   │   ├── state_estimate.py — StateEstimate
│   │   └── validation_record.py — ValidationRecord
│   ├── schemas/
│   │   └── ingest.py        — IngestRequest, IngestResponse (includes user_id)
│   ├── services/
│   │   ├── extractor.py     — HC payload → typed observation list
│   │   ├── baseline_service.py — recompute_baselines_for()
│   │   ├── trend_service.py — get_trend_series()
│   │   ├── constraint_engine.py — evaluate_constraints() [FROZEN]
│   │   ├── state_service.py — compute_and_store_state(), infer_state() [FROZEN]
│   │   ├── validation_service.py — create_or_update(), update_operator() [FROZEN]
│   │   └── agreement_service.py — get_summary(), get_by_state() [FROZEN]
│   └── api/v1/
│       ├── health.py, stats.py, ingest.py
│       ├── baselines.py, trends.py, state.py
│       ├── validation.py, agreement.py
└── alembic/versions/        — 7 migration files
```

---

## Design Decisions (frozen)

| Decision | Rationale |
|---|---|
| FHIR-mappable flat observations table | New metrics require no schema changes; future FHIR export straightforward |
| Aggregate over readRecords for steps/HR | Bypasses corrupt StepsRecord (BUG-002); aggregate API is more stable |
| IST timezone bucketing | Device is in India (Asia/Kolkata); all local-day operations use IST |
| TIMESTAMPTZ (UTC) everywhere | Convert to local time at read/display layer only |
| Separate INGEST_API_KEY / READ_API_KEY | Write scope and read scope never cross |
| Deterministic constraint cascade (not ML) | 3 metrics insufficient for ML; interpretability required for medical users |
| ON CONFLICT DO UPDATE with column exclusions | Operator columns (validation_status, operator_assessment) preserved on re-inference |
| version tags in validation_records only | constraints/state_estimates are mutable caches; immutable version snapshot belongs in validation layer |
| Evidence as JSONB | Schema-free analytical evolution without migrations |
| Render free tier | Single-user validation phase; upgrade when multi-user confirmed |
