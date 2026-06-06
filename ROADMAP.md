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
| sleep_end_hour present (IST-correct) | ✅ | value=6.35 (06:21 IST) |
| sleep_midpoint_hour present (IST-correct) | ✅ | value=4.075 (04:04 IST) |
| sleep_duration_hours present | ✅ | value=4.55 (4h 33m) |
| Values match Samsung Health | ✅ | start=01:48, end=06:21, dur=273min match device |
| Deduplication proven | ✅ | Same sleep session: 2nd sync blocked; steps (new timestamp) accepted |
| WorkManager autonomous sync | ✅ | Fired at 17:59:17 without user touch, POST status=202, DB 40→56 |

### Deferred to Phase 2

**BUG-006 — Resting HR fallback:** Samsung Health may not write `RestingHeartRateRecord` to Health Connect. Current implementation silently returns null. Deferred because Phase 1 objective was proving reliable pipeline and autonomous collection, not data completeness. BUG-006 is a data quality/modeling issue. Will implement `HeartRateRecord.BPM_MIN` (02:00–06:00 window) fallback in Phase 2.

---

## Current Phase: Phase 2 — Trend Analysis

**Status: BLOCKED — investigation required before implementation.**

### Pre-Phase 2 Investigation: Samsung Health vs Health Connect Sleep Model Discrepancy

**Priority: Must resolve before any circadian or recovery engine work.**

**Observed discrepancy:**

| Source | Start | End | Duration |
|---|---|---|---|
| Samsung Health (ground truth) | 1:48 AM | 8:07 AM | Time in bed: 6h 19m / Actual sleep: 5h 42m |
| Vigil (Health Connect) | 1:48 AM | 6:21 AM | 4h 33m |

**Questions to answer:**
1. What does Health Connect's `SleepSessionRecord` actually contain for this session? Is the end time `06:21` or `08:07`? Does HC expose a single session or multiple segments?
2. Does Samsung Health write sleep stage records to HC? If so, does the HC `SleepSessionRecord` include a `stages` list with REM/light/deep/awake segments that could explain the 5h 42m actual sleep figure?
3. Vigil's current selection window is `prev-18:00 → today-10:00`, minimum 180 min. Is `06:21` coming from a sub-session end or from Vigil's selection logic cutting the session short?
4. Is Samsung Health's "8:07 AM" end time a "time in bed" boundary that includes an awake-in-bed segment after the sleep session proper?

**Impact on Phase 2:** Trend analysis of `sleep_duration_hours` is meaningless if Vigil is capturing 4h 33m when true sleep was 5h 42m. Must understand the model before computing baselines.

**Investigation approach (next session):**
- Read raw `SleepSessionRecord` from HC for this session — log full record including `stages`
- Compare HC record fields to Samsung Health UI display
- Determine which field maps to "actual sleep" vs "time in bed"
- Decide on correct Vigil interpretation before Phase 2 data model is locked

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
1. Sleep model discrepancy investigation complete with documented finding
2. ≥7 days of real device observations in Postgres (`sleep_duration_hours` and `steps_today`)
3. BUG-001 (onResume permission recheck) fixed — prevents silent stale state that would block background collection
4. Decision made on resting HR fallback (BUG-006)

**Current DB state (2026-06-06):** 56 observations. Continuous sleep data starts today. 7-day gate reached ~2026-06-13.

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

---

## Active Work

### Immediate: Samsung Health vs Health Connect Sleep Model Investigation

Phase 1 complete. Phase 2 implementation blocked until sleep model discrepancy is understood.

**Discrepancy:** Samsung Health shows time-in-bed 6h 19m / actual sleep 5h 42m. Vigil captured 4h 33m (same session, different end time: 6:21 vs 8:07).

**Do next session:**
1. Read raw `SleepSessionRecord` from HC — log full object including `stages` list
2. Compare session boundaries and stage breakdowns to Samsung Health UI
3. Document finding: which field = "actual sleep", which = "time in bed"
4. Update `HealthRepository.readLastSleep()` if current selection is wrong

---

## Technical Debt

### Fix before Phase 2 implementation

| ID | File | Issue | Fix |
|----|------|-------|-----|
| BUG-001 | MainActivity.kt | onResume permission recheck missing — silent stale state after Settings grant | Add `onResume()` + `lifecycleScope.launch + getGrantedPermissions()` |
| BUG-004 | DashboardViewModel.kt | No error state when all HC queries fail — user sees `—` with no explanation | Add `loadError: String?` to DashboardUiState |
| — | DashboardViewModel.kt | `init { refresh() }` fires before Activity RESUMED, HC reads fail silently | Move initial POST to `LaunchedEffect` or lifecycle observer |
| — | HealthRepository.kt | `RawDashboard.lastSleep` is `SleepSessionRecord` (HC SDK type leaking into domain) | Extract `SleepSummary` data class — required before trend queries over sleep fields |

### Fix during Phase 2

| ID | File | Issue | Fix |
|----|------|-------|-----|
| BUG-006 | HealthRepository.kt | Resting HR always null — Samsung Health likely not writing `RestingHeartRateRecord` to HC | Implement `HeartRateRecord.BPM_MIN` (02:00–06:00 window) fallback. Deferred from Phase 1: not a pipeline reliability issue. |
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
| Sleep model discrepancy investigation | Engineering | Active — must resolve before Phase 2 implementation |
| ≥7 days real device observations | Time | Reached ~2026-06-13 |

---

## Prioritized Next Tasks

Phase 1 complete. Phase 2 entry criteria gate:

### P0 — Unblock Phase 2
1. **Investigate Samsung Health vs HC sleep model discrepancy** — read raw `SleepSessionRecord` including stages, compare to Samsung Health UI, document finding
2. **Fix BUG-001** — onResume permission recheck; prevents silent collection gaps between sessions

### P1 — Data quality before trend computation
3. **Extract `SleepSummary` domain model** — decouple from HC SDK type before trend queries
4. **Fix BUG-006** — implement `HeartRateRecord.BPM_MIN` fallback for resting HR
5. **Fix BUG-004** — add error surface to dashboard

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
