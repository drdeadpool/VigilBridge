# Vigil — Roadmap

Last updated: 2026-06-06. Reflects current repo + deployment state.

---

## ✅ Phase 1 COMPLETE — 2026-06-06

### Completion Evidence

| Criterion | Status | Evidence |
|---|---|---|
| POST /ingest returns 202 | ✅ | Logcat 17:29:40: `status=202 body={"accepted":8,...}` |
| Real observation rows in Postgres | ✅ | 56 observations, source=health_connect |
| sleep_start_hour present (IST-correct) | ✅ | value=1.8 (01:48 IST) |
| sleep_end_hour present (IST-correct) | ✅ | value=6.35 at Phase 1; corrected to 8.1167 (08:07 IST) by INV-001 |
| sleep_midpoint_hour present (IST-correct) | ✅ | value=4.075 — deprecated by INV-001 (midpoint model rejected) |
| sleep_duration_hours present | ✅ | value=4.55 at Phase 1; corrected to 5.70 by INV-001 from next night |
| Values match Samsung Health | ✅ | Post-INV-001: start=01:48, end=08:07, actual=5h42m, tib=6h19m |
| Deduplication proven | ✅ | Same sleep session: 2nd sync blocked; steps (new timestamp) accepted |
| WorkManager autonomous sync | ✅ | Fired at 17:59:17 without user touch, POST status=202, DB 40→56 |

### Deferred to Phase 2

**BUG-006 — Resting HR fallback:** Samsung Health does not write `RestingHeartRateRecord` to Health Connect on S24 Ultra. **Resolved 2026-06-24** (commit 0eb43fc): `HeartRateRecord.BPM_MIN` (02:00–06:00 window) fallback. Timestamp anchored to 02:00 physiological day (commit f514d95); migration `e1a2c4f9d3b7` applied in prod. BUG-006 closed.

---

## Current Phase: Phase 2 — Trend Analysis

**Status: ACTIVE.** Ingestion hardening deployed; data gate cleared 2026-06-19 (13 valid days, 660 valid obs). Baseline Engine v1 complete (commit c3c305c). Trend computation is next.

### INV-001 — RESOLVED 2026-06-06

Samsung Health splits one night's sleep into two `SleepSessionRecord` objects separated by short gaps (observed: 10-min gap at 06:21→06:31). Old model silently dropped session 2 (96 min) due to ≥180-min minimum filter.

**Fix applied:** `SleepMerger.kt` groups sessions within 30-min gaps, computes actual sleep from stage durations (LIGHT+DEEP+REM), excludes AWAKE/OUT_OF_BED. Backend extractor updated: adds `time_in_bed_hours`, `sleep_sessions_count`; `sleep_duration_hours` uses `actualSleepMinutes`.

**Verification (Android logcat):** `Merged sleep: sessions=2 actual=342min timeInBed=379min` — exact match to Samsung Health (5h42m actual, 6h19m in bed).

**New metrics in Postgres:** `time_in_bed_hours=6.3167`, `sleep_sessions_count=2.0`, `sleep_end_hour=8.1167`. Note: `sleep_duration_hours` for June 5-6 night is stuck at 4.55 (old row, `ON CONFLICT DO NOTHING`); correct 5.70 value appears from June 6-7 night onward.

### Phase 2 Definition of Done

All criteria must be proven with evidence:
- [ ] GET /trends/{user_id}?metric=sleep_duration_hours&period=7d returns valid JSON with ≥7 data points
- [ ] Personal baseline computed from ≥7 days of observations
- [ ] 7/14/30-day rolling averages correct (verified against raw observations)
- [ ] Anomaly detection flags a value >1.5 SD from baseline
- [ ] New `trends` table live in Postgres with Alembic migration
- [ ] Sleep model discrepancy resolved and Vigil captures correct sleep duration

### Phase 2 Entry Criteria

**Do not start Phase 2 implementation until:**
1. ✅ Sleep model investigation complete — INV-001 resolved 2026-06-06
2. ≥7 days of real device observations in Postgres — gate ~2026-06-13
3. ✅ BUG-001 fixed — 2026-06-06 (onResume permission recheck)
4. BUG-006 decision made (resting HR fallback)

**Current DB state (2026-06-06):** ~70 observations. Sleep model correct. 7-day gate ~2026-06-13.

---

---

## Completed Milestones

### 2026-06-02: v0.1 → v0.2 — Android Foundation

- [x] Health Connect SDK initialization and permission flow
- [x] Corrupt StepsRecord root-caused and bypassed (aggregate API)
- [x] MVVM architecture established
- [x] Room database (vitals_snapshots)
- [x] WorkManager 15-min background sync
- [x] KSP + AGP 9.x build compatibility fixed
- [x] Permission auto-transition fix (rememberLauncherForActivityResult)

### 2026-06-03: v0.2 → v0.3 — Backend + Network

- [x] FastAPI backend scaffolded (users, devices, observations schema)
- [x] POST /ingest endpoint with extractor service
- [x] FHIR-mappable observation schema
- [x] Alembic migrations
- [x] Docker + Render deployment
- [x] Android → Backend network layer (VigilApiClient, OkHttp)

### 2026-06-05 → 06: Timezone Fix + Sleep Timing

- [x] UTC bug fixed: sleep hours now use device timezone (Asia/Kolkata), not UTC
- [x] sleep_midpoint_hour and sleep_duration_hours added
- [x] tzdata==2025.2 in Docker requirements
- [x] Android payload includes timezone field
- [x] Sleep session selection (Option B: prev-18:00→today-10:00, ≥180min)

### 2026-06-06: Phase 1 Completion

- [x] GET /observations/recent endpoint added
- [x] DashboardViewModel.refresh() POSTs to backend (was read-only)
- [x] READ_HEALTH_DATA_IN_BACKGROUND added to manifest + permission sets
- [x] Deduplication: ON CONFLICT DO NOTHING + unique constraint migration (a3f92c1d4e87)
- [x] WorkManager network constraint bug fixed: `NetworkType.CONNECTED` + `UPDATE` policy
- [x] WorkManager autonomous sync proven: fired at 17:59:17, status=202, DB 40→56
- [x] **Phase 1 declared complete**

### 2026-06-06: Ingestion Hardening

- [x] Separate ingest and read API credentials
- [x] Protect `/stats` and `/observations/recent`
- [x] Fix failing SleepMerger fixture
- [x] Add typed Health Connect read outcomes
- [x] Add Room outbox with classified retry behavior
- [x] Add observation quality status and valid-only query helper
- [x] Verify rotated credentials, migration, and outbox against live deployment
  - Public `/stats` now returns 401; production docs return 404
  - Read key is independently scoped; ingest key cannot access read endpoints
  - Live quality counts confirmed and default recent query returned only valid rows
  - Device Room schema v2 confirmed; outbox drained after a 202 upload

---

## Active Work

### Wait for data accumulation gate (~2026-06-13)

INV-001 resolved and deployed. Sleep model correct, new metrics flowing. Data gate cleared 2026-06-19 (13 valid days, 660 valid obs). Phase 2 unblocked; Baseline Engine v1 shipped (commit c3c305c).

**While waiting — fix before Phase 2 starts:**
1. **BUG-006** — ✅ resolved/closed 2026-06-24 (commit 0eb43fc; anchor f514d95; prod migration e1a2c4f9d3b7 applied)

---

## Technical Debt

### Fix before Phase 2 implementation

| ID | File | Issue | Fix |
|----|------|-------|-----|
| — | DashboardViewModel.kt | `init { refresh() }` fires before Activity RESUMED, HC reads fail silently | Move initial POST to `LaunchedEffect` or lifecycle observer |
| — | Android sync | Verify Room outbox migration and retry behavior on device | Test queued upload across forced network failure |

### Fix during Phase 2

| ID | File | Issue | Fix |
|----|------|-------|-----|
| BUG-006 | HealthRepository.kt | Resting HR always null — Samsung Health not writing `RestingHeartRateRecord` to HC | ✅ **Resolved 2026-06-24** (0eb43fc + anchor f514d95): `HeartRateRecord.BPM_MIN` (02:00–06:00) fallback, anchored to 02:00 physiological day; prod migration e1a2c4f9d3b7 applied. |
| — | backend | Probe rows with UTC-buggy sleep_start_hour=17.0 in DB | Mark as probe in a `source_notes` field or filter in trend queries |

### Low priority (fix before Phase 3)

| ID | File | Issue | Fix |
|----|------|-------|-----|
| BUG-003 | DashboardScreen.kt | Magic literals 1 and 3 in UnavailableScreen | Replace with `HealthConnectClient` constants |
| BUG-005 | DashboardScreen.kt | `collectAsState` vs `collectAsStateWithLifecycle` | Add `lifecycle-runtime-compose` dep, swap import |
| BUG-007 | app/build.gradle.kts | versionName = "1.0" should be "0.3" | Set `versionCode=3, versionName="0.3"` |
| — | backend/README.md | GET /observations/recent not documented | Add endpoint docs |

---

## Blockers

| Blocker | Owner | Status |
|---------|-------|--------|
| Sleep model discrepancy (INV-001) | Engineering | **RESOLVED 2026-06-06** |
| ≥7 days real device observations | Time | Reached ~2026-06-13 |

---

## Prioritized Next Tasks

Phase 1 complete. Phase 2 entry criteria gate:

### P0 — Unblock Phase 2
1. ✅ ~~**Investigate Samsung Health vs HC sleep model discrepancy**~~ — DONE (INV-001, 2026-06-06)
2. ✅ ~~**Fix BUG-001**~~ — DONE (2026-06-06)

### P1 — Data quality before trend computation
3. **Deploy and verify ingestion hardening**
4. **Fix BUG-006** — implement `HeartRateRecord.BPM_MIN` fallback for resting HR
5. **Accumulate ≥7 valid days after data-quality filtering**

### P2 — Phase 2 implementation (after ~2026-06-13)
6. **`trends` table + Alembic migration**
7. **GET /trends/{user_id}** endpoint with 7/14/30-day rolling averages
8. **Personal baseline computation** (mean ± SD per metric)
9. **Anomaly detection** against baseline

### P3 — Cleanup (low urgency)
10. **Fix BUG-003, BUG-005, BUG-007**

---

## Future Phases

### Phase 2: Trend Analysis (current — investigation phase)
- 7/14/30-day rolling averages per metric
- Personal baseline computation (mean ± SD)
- Anomaly detection vs baseline
- New `trends` table
- GET /trends/{user_id}?metric=sleep_duration_hours&period=7d

**Gate:** Sleep model discrepancy resolved + ≥7 days of real device observations in Postgres + BUG-001 fixed.

### Phase 3: Circadian Analysis
- DLMO proxy from sleep midpoint time series
- Social jetlag (weekday vs weekend sleep timing)
- Sleep regularity index (SRI)
- Phase shift detection
- New `circadian_profiles` table

**Gate:** Trend engine live + ≥21 days of sleep_midpoint_hour data.

### Phase 4: Recovery Engine
- Composite daily recovery score (0-100)
- Inputs: HRV (when available), sleep duration, resting HR trend, step count
- Personal calibration (first 7 days = baseline establishment)
- New `recovery_scores` table

**Gate:** Circadian engine live + HR data confirmed from device.

### Phase 5: Intelligence Layer
- Claude API integration (claude-sonnet-4-6 default, claude-opus-4-8 for synthesis)
- Context injection: observations, trends, circadian phase, recovery score
- Clinician-readable narrative summaries
- Anomaly alerts with clinical context
- Read-only (no writes to DB from intelligence layer)

**Gate:** Recovery engine live + ≥30 days of data.

### Phase 6: Multi-User + Auth
- JWT auth replacing shared API key
- User registration/login
- Per-user data isolation
- Production infrastructure (non-free Render tier or alternative)

**Gate:** Intelligence layer validated on single user.

---

## Infrastructure State

| Component | State | Notes |
|-----------|-------|-------|
| Backend API | Live | vigilbridge.onrender.com, Render free tier |
| Postgres | Live | Render managed, 56 observations, IST-correct |
| Android APK | Installed | Debug build, R5CXB2KE0VF, WorkManager proven |
| GitHub repo | Current | drdeadpool/VigilBridge, auto-deploy from main |
| Migrations | Applied | 77f7b348bccf (initial), a3f92c1d4e87 (dedup unique constraint) |

---

## Version History

| Version | Date | Description |
|---------|------|-------------|
| v0.1 | 2026-06-02 | HC dashboard, corrupt record investigation |
| v0.2 | 2026-06-02 | MVVM refactor, Room, WorkManager |
| v0.3 | 2026-06-03–06 | Backend + network, timezone fix, sleep timing, dedup, autonomous sync |
