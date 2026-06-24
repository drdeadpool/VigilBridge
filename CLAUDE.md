# Vigil — Claude Engineering Guide

Last updated: 2026-06-24. Authoritative for all AI sessions.

---

## Project Goal

VigilBridge is a physiological intelligence platform for medical professionals (surgical residents, ICU staff). It reads biometric data from Health Connect on a Samsung Galaxy S24 Ultra, POSTs it to a FastAPI backend, stores it in Postgres, and will feed trend/circadian/recovery engines and ultimately a Claude intelligence layer.

This is Phase 4 of the BatmanOS personal roadmap. Target users require clinically interpretable data — correctness and reliability take precedence over features.

---

## Current Phase

**Phase 1: Reliable Data Ingestion** — ✅ COMPLETE (2026-06-06)

All criteria proven with evidence. WorkManager autonomous sync confirmed: status=202, DB 40→56, no user interaction. Deduplication live. IST-correct sleep timing in Postgres.

**Phase 2: Trend Analysis** — CURRENT PHASE. Data gate cleared 2026-06-19 (13 valid days, 660 valid obs). Vigil in passive data collection mode. Next major project: Research Agent MVP.

INV-001 resolved 2026-06-06: Samsung Health splits one night into two `SleepSessionRecord` objects with 10-min gap. `SleepMerger.kt` merges sessions within 30-min gaps and computes actual sleep from stage durations. New metrics: `time_in_bed_hours`, `sleep_sessions_count`.

BUG-006 fully closed 2026-06-24: Samsung Health confirmed NOT writing `RestingHeartRateRecord` to Health Connect on S24 Ultra. Fix: `HeartRateRecord.BPM_MIN` (02:00–06:00 device-local window) as fallback. Verified: 57 bpm in Postgres. Commit 0eb43fc. New permission: `READ_HEART_RATE`. Resting-HR timestamp anchored to 02:00 physiological day (commit f514d95); migration `e1a2c4f9d3b7` applied in prod, collapsing all syncs to one stable row/day.

Known investigation (deferred): sleep discrepancy — Samsung Health shows 7h55m, VigilBridge records 7h12m (43-min gap). Cause unknown.

Baseline Engine v1 shipped 2026-06-24 (commit c3c305c, 32/32 tests): per-metric mean/std/n/min/max over 7/14/30-day valid days + Severity v1, endpoints `GET /baselines/{user_id}` and `/baselines/{user_id}/status`. resting_hr anchor prerequisite resolved (see above). Remaining Phase 2 metric (not a baseline blocker): active_energy (`ActiveCaloriesBurnedRecord`). Trend computation is the next build.

---

## Priority Order

Never skip a level. Each is a prerequisite for the next.

1. **Reliable data ingestion** ✅
2. Validation and deduplication
3. Trend analysis (7/14/30-day)
4. Circadian analysis (sleep timing, phase)
5. Recovery scoring
6. Intelligence layer (Claude API)
7. Advanced predictive systems

Before implementing anything new, determine its priority level and confirm all prerequisite layers are complete.

---

## Model Selection Rules

### Use Opus for:
- Designing architecture
- Creating implementation plans for non-trivial changes
- Reviewing system design
- Root-cause analysis after repeated failures (≥2 failed fix attempts)
- Designing memory systems
- Designing the circadian, recovery, or intelligence engines
- Reviewing roadmap decisions
- Large refactors spanning ≥4 files
- Cross-system reasoning

### Use Sonnet for:
- Writing code (all routine implementation)
- Building/modifying API endpoints
- Database queries and migrations
- Refactoring within a planned scope
- Writing tests
- Documentation updates
- Routine debugging (first 2 attempts)

### Workflow for substantial tasks:
1. **Opus** → Analyze state, identify risks, produce implementation plan
2. Wait for approval if high-risk (touches deployed backend, schema migrations, auth)
3. **Sonnet** → Implement approved scope only
4. **Opus** → Review implementation, identify debt
5. **Sonnet** → Apply review fixes

---

## Development Principles

**Working over perfect.** A sync that produces real Postgres rows beats a beautifully architected system with no data.

**Reliability before sophistication.** Fix the broken ingestion before adding SpO2.

**Interpretation before expansion.** Understand what 16 probe observations mean before adding metric #17.

**Small increments.** One endpoint, one bug, one verification at a time.

**No speculative features.** Do not implement for hypothetical future requirements. No premature abstraction.

**Evidence-gated progression.** Each phase must produce verifiable evidence before the next begins. "It should work" is not evidence.

---

## Coding Standards

### Python (backend)
- FastAPI async everywhere. No sync DB calls.
- SQLAlchemy 2 async patterns only (`await db.execute(select(...))`)
- Pydantic models for all request/response bodies
- Return typed dicts from extractor functions, not model instances
- All timestamps stored as TIMESTAMPTZ (UTC). Convert to local time at read/display layer.
- Never commit secrets. API key comes from env via `config.py → Settings`.

### Kotlin (Android)
- MVVM with manual DI. No Hilt unless complexity justifies it.
- ViewModel owns state. Repository owns all HC queries.
- All HC reads in `HealthRepository` — never call HC client directly from ViewModel or Composable.
- Prefer aggregate APIs (`client.aggregate()`) over `readRecords()` to avoid per-record deserialization failures (see BUG-002).
- Health Connect reads require Activity at RESUMED state for foreground permission. WorkManager background reads require `READ_HEALTH_DATA_IN_BACKGROUND` permission.
- Health Connect reads return typed `MetricRead` outcomes: `Value`, `NoData`, or `Failure`.
- Never collapse a Health Connect exception into `null`; `null` is reserved for a successful read with no measurement.
- Local capture and network upload are separate. Every accepted capture writes a Room snapshot and immutable outbox payload in one transaction.
- Failed uploads remain in `sync_outbox` and are retried by `OutboxUploadWorker`.

### Both
- No inline comments unless the WHY is non-obvious.
- No error swallowing — log with tag + message, return null/empty, never crash.
- Timezone: always store UTC. IST computations happen in the extractor using IANA zoneinfo (`Asia/Kolkata`).

---

## Constraints

### Infrastructure
- Backend on Render free tier. Spins down after 15 min inactivity. First request after spindown takes ~30s.
- No message queue, no CDN, no caching layer — keep it simple.
- Android: no remote config, no analytics SDK.

### Health Connect
- Data is device-local. No cloud backup. Factory reset loses all history.
- Corrupt records exist (BUG-002 — a StepsRecord with startTime >= endTime). Aggregate API bypasses this.
- `pm grant` does not work for HC data permissions. User must grant via HC permission dialog.
- `READ_HEALTH_DATA_IN_BACKGROUND` required for WorkManager background reads. Must be in manifest AND runtime permission set AND granted by user.
- Samsung Health does NOT write `RestingHeartRateRecord` to HC on S24 Ultra (confirmed, 0 records in 13-day audit). `HeartRateRecord.BPM_MIN` (02:00–06:00 window) implemented as Stage 2 fallback in `readRestingHR()`. Permission `READ_HEART_RATE` required in manifest AND runtime permission set.

### Device
- Target: Samsung Galaxy S24 Ultra, serial R5CXB2KE0VF, ADB accessible.
- JAVA_HOME: `C:\Program Files\Android\Android Studio\jbr`
- ADB: `C:\Users\kaliv\AppData\Local\Android\Sdk\platform-tools\adb.exe`
- Build: `$env:JAVA_HOME="C:\Program Files\Android\Android Studio\jbr"; .\gradlew assembleDebug`

---

## Documentation Maintenance Rules

Whenever architecture changes → update ARCHITECTURE.md before next commit.
Whenever priorities or phase changes → update ROADMAP.md before next commit.
Whenever workflow, standards, or constraints change → update CLAUDE.md before next commit.
Never let docs lag more than one session behind code.

Keep BUGS.md current. Close bugs by marking status "Resolved" with fix description. Add new bugs discovered mid-session.

---

## Known Critical Bugs (summary)

| ID | Status | Description |
|----|--------|-------------|
| BUG-001 | Resolved | onResume permission recheck implemented |
| BUG-002 | Bypassed | Corrupt StepsRecord — aggregate API workaround in place |
| BUG-003 | Open | UnavailableScreen uses magic int literals |
| BUG-004 | Resolved | Typed HC outcomes distinguish no-data, partial failure, and total failure |
| BUG-005 | Open | collectAsState vs collectAsStateWithLifecycle |
| BUG-006 | Resolved | HeartRateRecord.BPM_MIN fallback (02:00–06:00), 57 bpm verified in Postgres. Commit 0eb43fc. |
| BUG-007 | Open | versionName = "1.0" should be "0.3" |
| BUG-008 | Resolved | API key exposure + unauth read endpoints — rotated key, READ_API_KEY, docs disabled (2026-06-06) |
| BUG-009 | Open (Deferred) | Sleep dated by local sleep-start, no physiological-night anchor → Jun 20 ×2 / Jun 21 ×0. Defer until after Recovery Engine. |
| BUG-010 | Open (Deferred) | Dashboard sleep card shows only actual sleep, not time-in-bed/awake/efficiency → apparent vs-Samsung gap. UX only; data already in Postgres. Defer until after Recovery Engine. |

See BUGS.md for full detail and recommended fixes.

---

## Session Start Protocol

1. Read CLAUDE.md (this file)
2. Read ROADMAP.md for current state
3. Verify backend health: `curl https://vigilbridge.onrender.com/health`
4. Check current DB state: `curl https://vigilbridge.onrender.com/stats -H "X-Api-Key: <READ_API_KEY>"`
5. Check device connected: `adb -s R5CXB2KE0VF devices`
6. Determine which priority level the current task belongs to
7. Confirm prerequisite phases are complete before proceeding
