# Vigil Backend

FastAPI backend for the Vigil physiological intelligence platform.

Accepts Health Connect webhook payloads → stores as FHIR-mappable observations in Postgres → feeds the trend, circadian, and recovery engines.

---

## Stack

| Component | Technology |
|-----------|-----------|
| API | FastAPI + uvicorn |
| Database | PostgreSQL 16 |
| ORM | SQLAlchemy 2.0 (async) |
| Migrations | Alembic |
| Containers | Docker + Compose |

---

## Quick Start (Docker)

```bash
cp .env.example .env
# Edit .env if needed — defaults work for local Docker

docker compose up -d
# Postgres starts, then API starts on :8000

# Apply migrations
docker compose exec api python -m alembic upgrade head

# Verify
curl http://localhost:8000/health
```

---

## Quick Start (Local)

Requires Python 3.12+, a running Postgres instance.

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# Set DATABASE_URL to point at your Postgres

# Apply migrations
DATABASE_URL=postgresql+asyncpg://vigil:vigil@localhost:5432/vigil \
  python -m alembic upgrade head

# Run
uvicorn app.main:app --reload
```

---

## Endpoints

### `GET /health`

Database connectivity check.

```json
{"status": "ok", "database": "connected"}
```

---

### `POST /ingest`

Ingest a Health Connect webhook payload. Extracts typed observations and stores them.

**Header:** `x-api-key: <INGEST_API_KEY>`

**Body:**
```json
{
  "user_external_id": "R5CXB2KE0VF",
  "device_identifier": "samsung-s24-ultra",
  "device_model": "SM-S928B",
  "platform": "android",
  "source_app": "health_connect",
  "payload": {
    "record_type": "StepsRecord",
    "start_time": "2026-06-05T00:00:00Z",
    "count": 8432
  }
}
```

**VigilBridge snapshot format also accepted:**
```json
{
  "user_external_id": "R5CXB2KE0VF",
  "device_identifier": "samsung-s24-ultra",
  "payload": {
    "record_type": "snapshot",
    "timestampMs": 1749168000000,
    "stepsToday": 8432,
    "steps7d": 61234,
    "sleepDurationMinutes": 423,
    "restingHrBpm": 52
  }
}
```

**Response (202):**
```json
{
  "accepted": 4,
  "observations": [
    {"id": "...", "metric_type": "steps_today", "value": 8432.0, "unit": "steps", ...}
  ]
}
```

---

### `GET /stats`

Summary of stored data.

```json
{
  "total_observations": 1247,
  "observation_types": {
    "steps_today": 312,
    "sleep_duration_minutes": 289,
    "resting_hr_bpm": 301
  },
  "latest_timestamp": "2026-06-05T14:23:00+00:00"
}
```

---

## Supported HC Record Types

| record_type | Extracted metric_type | Unit |
|-------------|----------------------|------|
| `StepsRecord` | `steps` | steps |
| `SleepSessionRecord` | `sleep_duration` | min |
| `HeartRateRecord` | `heart_rate` | bpm |
| `RestingHeartRateRecord` | `resting_hr` | bpm |
| `OxygenSaturationRecord` | `spo2` | % |
| `RespiratoryRateRecord` | `respiratory_rate` | breaths/min |
| `snapshot` (VigilBridge) | `steps_today`, `steps_7d`, `sleep_duration_minutes`, `resting_hr_bpm` | various |

Unknown record types are stored with `metric_type=<type>` and `value=null`. The raw payload is always preserved.

---

## FHIR Mapping

The `observations` table is designed for future FHIR R4 export:

| Column | FHIR Field |
|--------|-----------|
| `metric_type` | `Observation.code.coding[0].code` (LOINC) |
| `value` + `unit` | `Observation.valueQuantity` |
| `timestamp` | `Observation.effectiveDateTime` |
| `source` | `Observation.device.display` |
| `raw_payload` | `Observation.extension` |

---

## Project Structure

```
backend/
├── app/
│   ├── main.py              ← FastAPI app, middleware, router registration
│   ├── config.py            ← Settings from .env
│   ├── database.py          ← Async SQLAlchemy engine + session
│   ├── models/
│   │   ├── user.py          ← User table
│   │   ├── device.py        ← Device table
│   │   └── observation.py   ← Observation table (FHIR-mappable)
│   ├── schemas/
│   │   └── ingest.py        ← Pydantic request/response models
│   ├── services/
│   │   └── extractor.py     ← HC payload → typed observations
│   └── api/v1/
│       ├── ingest.py        ← POST /ingest
│       ├── health.py        ← GET /health
│       └── stats.py         ← GET /stats
├── alembic/
│   ├── env.py               ← Reads DATABASE_URL env var
│   └── versions/
│       └── 77f7b348bccf_initial_schema.py
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## Running Migrations

```bash
# Apply all pending
python -m alembic upgrade head

# Roll back one
python -m alembic downgrade -1

# Check current revision
python -m alembic current
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://vigil:vigil@localhost:5432/vigil` | Async Postgres URL |
| `POSTGRES_USER` | `vigil` | Docker Compose only |
| `POSTGRES_PASSWORD` | `vigil` | Docker Compose only |
| `POSTGRES_DB` | `vigil` | Docker Compose only |
| `INGEST_API_KEY` | `changeme` | Bearer key for POST /ingest |
| `LOG_LEVEL` | `INFO` | Python logging level |
