# Vigil — Architecture

Last updated: 2026-06-06. Reflects current deployed code.

---

## System Overview

```
Samsung Galaxy S24 Ultra
  └─ Samsung Health (writes biometrics to Health Connect)
       └─ Health Connect (on-device health data store)
            └─ VigilBridge Android App
                 ├─ Foreground: HealthRepository reads HC → Dashboard UI
                 ├─ Background: WorkManager (15-min) reads HC → Room
                 └─ Network: VigilApiClient POSTs snapshot → Render
                                                                  │
                              vigilbridge.onrender.com ◄──────────┘
                                    │
                              FastAPI + uvicorn
                                    │
                              extract_observations()
                                    │
                              PostgreSQL 16 (Render managed)
                                    │
                         [Future: Trend / Circadian / Recovery Engines]
                                    │
                         [Future: Claude Intelligence Layer]
```

---

## Data Flow

### Foreground sync (user-triggered)

```
User taps Refresh
  → DashboardViewModel.refresh()
  → HealthRepository.load()
      ├─ client.aggregate(steps today/7d/30d) [SecurityException if not RESUMED]
      ├─ client.readRecords(SleepSessionRecord, window prev-18:00→today-10:00, ≥180min filter)
      └─ client.aggregate(RestingHeartRateRecord.BPM_AVG, 7d)
  → dao.insert(VitalsSnapshot) [Room local write]
  → VigilApiClient.postSnapshot(context, raw, timestamp) [HTTP POST]
      → POST https://vigilbridge.onrender.com/ingest
          → extract_observations(payload)
          → INSERT INTO observations (multiple rows per snapshot)
          → Response: {accepted: N, observations: [...]}
  → DashboardUiState update → Compose recompose
```

### Background sync (WorkManager, 15-min periodic)

```
WorkManager fires VitalsSyncWorker
  → Check HC SDK available
  → Check REQUIRED_PERMISSIONS all granted (includes READ_HEALTH_DATA_IN_BACKGROUND)
  → HealthRepository(client, dao).load()
      [same HC reads as foreground, but requires READ_HEALTH_DATA_IN_BACKGROUND]
  → dao.insert(VitalsSnapshot)
  → VigilApiClient.postSnapshot(...) [fire-and-forget, failure does NOT retry worker]
  → Result.success()
```

### Backend ingestion path

```
POST /ingest (Header: X-Api-Key)
  → Auth check (constant-time compare)
  → Upsert User (by user_external_id = Android device ID)
  → Upsert Device (by user_id + device_identifier)
  → extract_observations(payload, source)
      → Dispatch by payload.record_type:
          "snapshot" → _extract_vigil_snapshot()
              ├─ steps_today, steps_7d, steps_30d, sleep_duration_minutes, resting_hr_bpm
              └─ sleep timing (start_ms + end_ms + timezone → IST-aware hours):
                  sleep_start_hour, sleep_end_hour, sleep_midpoint_hour, sleep_duration_hours
          "StepsRecord" → _extract_steps()
          "SleepSessionRecord" → _extract_sleep()
          [other types supported]
  → INSERT INTO observations (N rows, raw_payload preserved as JSONB)
  → 202 Accepted + {accepted: N, observations: [...]}
```

---

## Android Architecture

### Package structure

```
com.batman.vigilbridge/
├── MainActivity.kt          — Activity entry point
│                              HC SDK check, permission launcher, WorkManager schedule
│
├── data/
│   ├── HealthRepository.kt  — All HC queries (aggregate + readRecords)
│   │                          Room write after every load
│   │                          RawDashboard data class (steps, sleep, HR)
│   ├── VitalsSnapshot.kt    — Room entity: vitals_snapshots table
│   ├── VitalsDao.kt         — insert, getLatest, getRecent(n)
│   └── VigilDatabase.kt     — Room singleton (vigil.db)
│
├── network/
│   └── VigilApiClient.kt    — OkHttp singleton, POST /ingest
│                              Builds JSON payload from RawDashboard
│                              Reads VIGIL_BASE_URL and INGEST_API_KEY from BuildConfig
│
├── ui/
│   ├── DashboardScreen.kt   — All Composables
│   │                          VigilScreen, Dashboard, PermissionScreen, MetricCard
│   │                          Creates repo via LocalContext → hands to ViewModel
│   └── DashboardViewModel.kt — StateFlow<DashboardUiState>
│                               refresh() = HC load + Room write + POST
│                               toUiState() = RawDashboard → formatted strings
│
└── work/
    └── VitalsSyncWorker.kt  — CoroutineWorker, 15-min periodic
                               Same load() path as foreground + POST
```

### MVVM pattern

```
View (Composables) ←─ StateFlow<DashboardUiState> ── ViewModel
                   ──── onRefresh() ────────────────→ ViewModel.refresh()
                                                           │
                                               HealthRepository.load()
                                                     │         │
                                               HC Client    Room DAO
                                                     │
                                               VigilApiClient.postSnapshot()
```

Manual dependency injection. No Hilt. HealthRepository created in Composable via LocalContext, passed to ViewModel factory.

### Health Connect permissions

| Permission | Purpose | Grant method |
|-----------|---------|-------------|
| health.READ_STEPS | Step count aggregates | HC permission dialog |
| health.READ_SLEEP | Sleep session records | HC permission dialog |
| health.READ_RESTING_HEART_RATE | Resting HR aggregates | HC permission dialog |
| health.READ_HEALTH_DATA_IN_BACKGROUND | WorkManager background reads | HC permission dialog |

All four must be in AndroidManifest.xml AND in `PERMISSIONS` set AND granted by user. `pm grant` does not work for HC data permissions.

### Known timing issue

`DashboardViewModel.init { refresh() }` fires during `onCreate → setContent` before Activity reaches RESUMED state. HC treats this as background — aggregate queries fail with READ_HEALTH_DATA_IN_BACKGROUND error even when app appears foreground. User-triggered Refresh (from a visually displayed Activity) works correctly.

---

## FastAPI Backend Architecture

### Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| API framework | FastAPI | 0.115 |
| ASGI server | uvicorn | 0.34 |
| ORM | SQLAlchemy async | 2.0 |
| Migrations | Alembic | 1.15 |
| DB driver | asyncpg | 0.30 |
| Validation | Pydantic v2 | 2.10 |
| Python | CPython | 3.12 |
| Container | Docker | slim |
| Deployment | Render free tier | |

### File structure

```
backend/
├── app/
│   ├── main.py           — FastAPI app, CORS, router registration
│   ├── config.py         — Settings (DATABASE_URL, INGEST_API_KEY, LOG_LEVEL)
│   │                       Normalizes postgres:// → postgresql+asyncpg://
│   ├── database.py       — Async engine, session factory, Base
│   ├── models/
│   │   ├── user.py       — User (id UUID PK, external_id, display_name)
│   │   ├── device.py     — Device (id, user_id FK, identifier, model, platform)
│   │   └── observation.py — Observation (FHIR-mappable, see schema below)
│   ├── schemas/
│   │   └── ingest.py     — IngestRequest, IngestResponse, ObservationOut (Pydantic)
│   ├── services/
│   │   └── extractor.py  — HC payload → typed observation list
│   └── api/v1/
│       ├── ingest.py     — POST /ingest
│       ├── health.py     — GET /health
│       └── stats.py      — GET /stats, GET /observations/recent
└── alembic/
    └── versions/77f7b348bccf_initial_schema.py — users, devices, observations
```

### Endpoints

| Method | Path | Auth | Returns |
|--------|------|------|---------|
| POST | /ingest | X-Api-Key | 202 + {accepted, observations} |
| GET | /health | None | {status, database} |
| GET | /stats | X-Api-Key | {total, types, latest_timestamp} |
| GET | /observations/recent | X-Api-Key | [{id, metric_type, value, unit, timestamp, source, timezone}] |

`GET /observations/recent` accepts `?limit=N` (1-100, default 20) and `?metric_type=sleep_start_hour`.

---

## Database Architecture

### Schema

```sql
-- Users (identified by Android device ID or account ID)
users (
    id          UUID PK,
    external_id VARCHAR(255) UNIQUE NOT NULL,  -- Android device ID
    display_name VARCHAR(255),
    created_at  TIMESTAMPTZ,
    updated_at  TIMESTAMPTZ
)

-- Devices (one per physical device per user)
devices (
    id                 UUID PK,
    user_id            UUID FK → users.id,
    device_identifier  VARCHAR(255),  -- Android device model
    device_model       VARCHAR(255),
    platform           VARCHAR(64),   -- "android"
    source_app         VARCHAR(255),  -- "health_connect"
    created_at         TIMESTAMPTZ,
    last_seen_at       TIMESTAMPTZ
)

-- Observations (FHIR-mappable flat log — one row per metric per sync)
observations (
    id           UUID PK,
    user_id      UUID FK → users.id,
    device_id    UUID FK → devices.id,
    metric_type  VARCHAR(128) INDEXED,  -- e.g. "sleep_start_hour"
    value        NUMERIC(12,4),
    unit         VARCHAR(64),
    timestamp    TIMESTAMPTZ INDEXED,
    source       VARCHAR(128),          -- "health_connect"
    raw_payload  JSONB,                 -- full original payload preserved
    created_at   TIMESTAMPTZ
)
```

### Indexes

```
ix_users_external_id       (unique)
ix_devices_user_id
ix_observations_user_id
ix_observations_device_id
ix_observations_metric_type
ix_observations_timestamp
```

### FHIR mapping

| Column | FHIR R4 Field |
|--------|--------------|
| metric_type | Observation.code.coding[0].code (LOINC) |
| value + unit | Observation.valueQuantity |
| timestamp | Observation.effectiveDateTime |
| source | Observation.device.display |
| raw_payload | Observation.extension |

### Metric types currently stored

From VigilBridge snapshot payloads:
- `steps_today` (steps)
- `steps_7d` (steps)
- `steps_30d` (steps)
- `sleep_duration_minutes` (min)
- `sleep_duration_hours` (hours)
- `sleep_start_hour` (hour, IST-aware float, e.g. 22.5 = 10:30 PM)
- `sleep_end_hour` (hour, IST-aware float)
- `sleep_midpoint_hour` (hour, IST-aware float)
- `resting_hr_bpm` (bpm)

From direct HC record payloads (extractor also supports):
- `steps`, `sleep_duration`, `heart_rate`, `resting_hr`, `spo2`, `respiratory_rate`

---

## Extractor Service Architecture

`backend/app/services/extractor.py`

```
extract_observations(payload, source)
  → dispatch by payload["record_type"]
  → _extract_vigil_snapshot(payload, source)
      → scalar fields (steps, HR, duration)
      → sleep timing block:
          timezone = payload["timezone"]  (IANA: "Asia/Kolkata")
          start_utc = parse_ts(sleepStartMs)
          end_utc = parse_ts(sleepEndMs)
          local_hour(utc_dt) = dt.astimezone(ZoneInfo(tz)).hour + min/60 + sec/3600
          → sleep_start_hour = local_hour(start_utc)
          → sleep_end_hour = local_hour(end_utc)
          → sleep_midpoint_hour = local_hour((start + end) / 2)
          → sleep_duration_hours = (end - start).total_seconds() / 3600
  → returns list[dict] ready for Observation INSERT
```

UTC correction: earlier code returned UTC hour (17.0 for 22:30 IST). Fixed in commit `6c9d6ad` by passing device timezone via `ZoneId.systemDefault().id` and using `ZoneInfo` on the backend. tzdata==2025.2 in requirements.txt for Docker slim compatibility.

---

## Local Android Persistence (Room)

```
vitals_snapshots table
  id             INTEGER PK autoincrement
  timestampMs    INTEGER (epoch ms, UTC)
  stepsToday     INTEGER?
  steps7d        INTEGER?
  steps30d       INTEGER?
  sleepDurationMinutes INTEGER?
  sleepStartMs   INTEGER? (epoch ms, UTC)
  sleepEndMs     INTEGER? (epoch ms, UTC)
  restingHrBpm   INTEGER?
```

Room is used for: local persistence between syncs, dashboard startup cache (planned), offline resilience.

---

## Future Architecture (not yet implemented)

### Trend Engine (Phase 2)
Reads Postgres observations, computes 7/14/30-day rolling averages, detects anomalies vs personal baseline. New `trends` table with `user_id, metric_type, period, value, computed_at`.

### Circadian Engine (Phase 3)
Uses `sleep_start_hour`, `sleep_end_hour`, `sleep_midpoint_hour` time series to compute circadian phase (DLMO proxy), social jetlag, sleep regularity index. Requires ≥14 days of observations.

### Recovery Engine (Phase 4)
Composite score from HRV, sleep duration, resting HR trend, step count. Produces a daily 0-100 recovery score. Requires Circadian Engine output as input.

### Intelligence Layer (Phase 5)
Claude API integration. Receives structured context (observations, trends, recovery scores, circadian phase) and produces clinician-readable narrative summaries, alerts, and recommendations. Read-only — does not write to DB.

---

## Major Design Decisions

### FHIR-mappable observation schema
Single flat `observations` table (metric_type + value + unit + timestamp) instead of typed tables per metric. Rationale: new metrics require no schema changes; future FHIR export is straightforward; query patterns (latest by type, range by time) work efficiently with the current indexes.

### Aggregate over readRecords for steps/HR
`client.aggregate()` delegates computation to HC service, bypassing per-record deserialization. Avoids BUG-002 (corrupt StepsRecord). Principle: prefer aggregate where only aggregate values are needed.

### Sleep window: prev-18:00 → today-10:00, ≥180min filter
Samsung Health records sleep sessions that can begin before midnight. A 24h lookback misses early-evening sessions. An 18:00-yesterday anchor captures any realistic bedtime. The ≥180min filter excludes short naps. This is Option B from sleep selection investigation.

### Timezone in payload
Android sends `"timezone": "Asia/Kolkata"` (ZoneId.systemDefault().id). Backend uses Python zoneinfo with tzdata package to compute local hours. UTC hours were stored prior to commit 6c9d6ad — all 16 existing observations may have incorrect sleep timing values.

### Render free tier + single Postgres instance
Acceptable for development and early validation. Will need to upgrade before multi-user production. Free tier spins down after 15min inactivity — first request takes ~30s.

### No auth system yet
API key auth (shared secret in X-Api-Key header). Single user. No JWT, no OAuth. Appropriate for current single-device validation phase.

### Manual DI over Hilt
App complexity doesn't justify Hilt. ViewModel gets repository via factory pattern. If dependency graph grows past 3 levels, add Hilt.
