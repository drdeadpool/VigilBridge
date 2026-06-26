# Vigil — Claude Engineering Guide

Last updated: 2026-06-26. Authoritative for all AI sessions.

---

## Project Goal

Vigil is an evidence-driven Human State Intelligence platform for medical professionals (surgical residents, ICU staff). It reads biometric data from Health Connect on a Samsung Galaxy S24 Ultra, persists it in Postgres, and infers daily Human State through a deterministic constraint cascade. Engineering Foundation is complete and frozen. Vigil is now in Scientific Operations.

---

## Current Phase

**Scientific Operations — ACTIVE** (2026-06-26 onwards)

Engineering Foundation is FROZEN. All systems at v1.0.

Default working mode: **protect architectural integrity**. Challenge requests for new features unless supported by operational evidence.

The engineering loop:
```
Operate → Collect Evidence → Validate → Measure → Review → Implement Small Improvements → Benchmark → Deploy
```

Every proposed implementation must answer: **"What operational evidence justifies this?"**
If no evidence exists, defer.

---

## What Is Frozen (do not modify without ADR + evidence)

| System | What frozen means |
|---|---|
| Constraint Engine | No new rules, no threshold changes |
| Human State Estimator | No new states, no cascade changes |
| Validation Engine | No new status vocabulary, no operator flow changes |
| Agreement Engine | No formula changes, no new analytics without test evidence |
| Persistence Model | No new tables without ADR, no breaking schema changes |
| API v1.0 | No breaking changes; additive read-only endpoints permitted with tests |

Bug fixes permitted with test evidence. New read-only analytics endpoints permitted with test evidence. No ML, LLM, prediction, or personalization.

---

## Priority Order (Engineering Foundation Complete)

Levels are now operational, not implementation phases:

1. **System reliability** — ingest pipeline must continue firing correctly
2. **Operator assessments** — recording PATCH /validation/{id} entries
3. **Agreement monitoring** — periodic GET /agreement/{user_id} review
4. **Evidence accumulation** — ≥30 days of assessed records before engineering work
5. **Small evidence-justified improvements** — only after level 4 complete

Do not skip levels. Do not implement at level 5 without completing level 4.

---

## Model Selection Rules

### Use Opus for:
- Designing architecture changes
- Reviewing system design
- Root-cause analysis after repeated failures (≥2 failed fix attempts)
- Designing future engines (Insight, Circadian, Recovery, Intelligence)
- Reviewing roadmap decisions
- Cross-system reasoning

### Use Sonnet for:
- All routine implementation
- API endpoints, migrations, tests
- Debugging (first 2 attempts)
- Documentation updates

---

## Development Principles

**Evidence before implementation.** No feature ships without operational data justifying it.

**Deterministic over probabilistic.** The system produces auditable, traceable inferences. No black boxes.

**Interpretability required.** Target users are medical professionals. Every state traces to named constraints, z-scores, and raw sensor values.

**No speculative features.** Do not implement for hypothetical future requirements.

**No ML, LLM, or scoring layers** until Recovery Engine phase with sufficient training data.

---

## Coding Standards

### Python (backend)
- FastAPI async everywhere. No sync DB calls.
- SQLAlchemy 2 async patterns only (`await db.execute(select(...))`)
- Pydantic models for all request/response bodies
- All timestamps stored as TIMESTAMPTZ (UTC). Convert to local time at read/display layer.
- Never commit secrets. API key comes from env via `config.py → Settings`.
- IST timezone (Asia/Kolkata) for local-day bucketing in constraint/state/baseline queries.
- ON CONFLICT DO UPDATE pattern for upserts throughout.

### Kotlin (Android)
- MVVM with manual DI. No Hilt unless complexity justifies it.
- ViewModel owns state. Repository owns all HC queries.
- All HC reads in `HealthRepository` — never call HC client directly from ViewModel or Composable.
- Health Connect reads return typed `MetricRead` outcomes: `Value`, `NoData`, or `Failure`.
- Local capture and network upload are separate. Every accepted capture writes Room snapshot + immutable outbox payload in one transaction.

### Both
- No inline comments unless the WHY is non-obvious.
- No error swallowing — log with tag + message, return null/empty, never crash.
- Timezone: always store UTC. IST computations happen in the extractor using IANA zoneinfo (`Asia/Kolkata`).

---

## Constraints

### Infrastructure
- Backend on Render free tier. Spins down after 15 min inactivity (~30s cold start).
- No message queue, no CDN, no caching layer.

### Health Connect / Samsung Health (confirmed OEM siloing on S24 Ultra)
- `RestingHeartRateRecord` not written by Samsung Health → fallback: `HeartRateRecord.BPM_MIN` 02:00–06:00 window (committed, deployed, verified 57 bpm)
- `ActiveCaloriesBurnedRecord` not written by Samsung Health → `active_energy` absent from all payloads. No code fix possible — OEM change required.
- `READ_HEALTH_DATA_IN_BACKGROUND` required for WorkManager background reads.
- `pm grant` does not work for HC data permissions.

### Device
- Target: Samsung Galaxy S24 Ultra, serial R5CXB2KE0VF, ADB accessible.
- JAVA_HOME: `C:\Program Files\Android\Android Studio\jbr`
- ADB: `C:\Users\kaliv\AppData\Local\Android\Sdk\platform-tools\adb.exe`
- Android ID (external_id): `aad1d7da558d58f2`
- User UUID: `37c5d374-d624-404f-ae6f-50a6781601bf`
- Build: `$env:JAVA_HOME="C:\Program Files\Android\Android Studio\jbr"; .\gradlew assembleDebug`

---

## Known Open Bugs

| ID | Status | Description |
|---|---|---|
| BUG-001 | Resolved | onResume permission recheck implemented |
| BUG-002 | Bypassed | Corrupt StepsRecord — aggregate API workaround |
| BUG-003 | Open | UnavailableScreen uses magic int literals |
| BUG-004 | Resolved | Typed HC outcomes |
| BUG-005 | Open | collectAsState vs collectAsStateWithLifecycle (negligible impact) |
| BUG-006 | Resolved | HeartRateRecord.BPM_MIN fallback (02:00–06:00), 57 bpm verified |
| BUG-007 | Open | versionName cosmetic mismatch |
| BUG-008 | Resolved | API key rotation + auth gates |
| BUG-009 | Deferred | Sleep dated by sleep-start (no physiological-night anchor) |
| BUG-010 | Deferred | Dashboard shows actual sleep only, not time-in-bed |

---

## Documentation Maintenance Rules

Whenever architecture changes → update ARCHITECTURE.md before next commit.
Whenever priorities or phase changes → update ROADMAP.md before next commit.
Whenever workflow, standards, or constraints change → update CLAUDE.md before next commit.
Never let docs lag more than one session behind code.
Keep BUGS.md current. Close bugs by marking "Resolved" with fix description.

---

## Session Start Protocol

1. Read CLAUDE.md (this file)
2. Read PROJECT_STATE.md for current state and production stats
3. Verify backend health: `curl https://vigilbridge.onrender.com/health`
4. Check DB state: `curl https://vigilbridge.onrender.com/stats -H "X-Api-Key: <READ_API_KEY>"`
5. Check device: `adb -s R5CXB2KE0VF devices`
6. **Ask: what operational evidence justifies the proposed task?**
7. If no evidence exists: record an operator assessment instead of writing code
