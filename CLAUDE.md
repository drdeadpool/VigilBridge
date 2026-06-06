# Vigil — Claude Engineering Guide

Last updated: 2026-06-06. Authoritative for all AI sessions.

---

## Project Goal

VigilBridge is a physiological intelligence platform for medical professionals (surgical residents, ICU staff). It reads biometric data from Health Connect on a Samsung Galaxy S24 Ultra, POSTs it to a FastAPI backend, stores it in Postgres, and will feed trend/circadian/recovery engines and ultimately a Claude intelligence layer.

This is Phase 4 of the BatmanOS personal roadmap. Target users require clinically interpretable data — correctness and reliability take precedence over features.

---

## Current Phase

**Phase 1: Reliable Data Ingestion** — ✅ COMPLETE (2026-06-06)

All criteria proven with evidence. WorkManager autonomous sync confirmed: status=202, DB 40→56, no user interaction. Deduplication live. IST-correct sleep timing in Postgres.

**Phase 2: Trend Analysis** — CURRENT PHASE. Blocked on investigation.

Active blocker: Samsung Health vs Health Connect sleep model discrepancy. Samsung Health reports 5h 42m actual sleep / 6h 19m time-in-bed. Vigil captured 4h 33m (end time 6:21 vs 8:07). Must read raw `SleepSessionRecord` including `stages`, compare to Samsung Health, and determine correct mapping before trend baselines are computed.

Do not begin Phase 2 implementation, Phase 3 (Circadian Engine), Phase 4 (Recovery Engine), or UI improvements until sleep model investigation is complete and ≥7 days of observations exist in Postgres (~2026-06-13).

---

## Priority Order

Never skip a level. Each is a prerequisite for the next.

1. **Reliable data ingestion** ← current
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
- `RawDashboard` couples ViewModel to HC SDK types. Acceptable until Phase 2; extract domain models before trend analysis.

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
- Samsung Health may not write `RestingHeartRateRecord` to HC. Use `HeartRateRecord.BPM_MIN` (2am–6am) as fallback if confirmed unavailable (BUG-006).

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
| BUG-001 | Open | onResume permission recheck missing |
| BUG-002 | Bypassed | Corrupt StepsRecord — aggregate API workaround in place |
| BUG-003 | Open | UnavailableScreen uses magic int literals |
| BUG-004 | Open | No error surface when all HC queries fail |
| BUG-005 | Open | collectAsState vs collectAsStateWithLifecycle |
| BUG-006 | Open | RestingHR unverified on S24 Ultra |
| BUG-007 | Open | versionName = "1.0" should be "0.3" |

See BUGS.md for full detail and recommended fixes.

---

## Session Start Protocol

1. Read CLAUDE.md (this file)
2. Read ROADMAP.md for current state
3. Verify backend health: `curl https://vigilbridge.onrender.com/health`
4. Check current DB state: `curl https://vigilbridge.onrender.com/stats -H "X-Api-Key: 0dc8144910936507989abc28e059d7d5"`
5. Check device connected: `adb -s R5CXB2KE0VF devices`
6. Determine which priority level the current task belongs to
7. Confirm prerequisite phases are complete before proceeding
