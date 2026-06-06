# Vigil — Roadmap

Last updated: 2026-06-06. Reflects current repo + deployment state.

---

## Current Phase: Phase 1 — Reliable Data Ingestion

**Status: 90% complete. Blocked on HC permission re-grant.**

### Definition of Done (Phase 1)

All must be verified with evidence, not assumed:
- [ ] POST /ingest returns 202
- [ ] Real observation row in Postgres (not probe payload)
- [ ] sleep_start_hour, sleep_end_hour, sleep_midpoint_hour, sleep_duration_hours all present
- [ ] Values match Samsung Health displayed values
- [ ] Evidence shown (logcat + curl output)

### Active Blocker

HC permissions were reset when APK was reinstalled (2026-06-06). User must physically unlock device, open VigilBridge, and re-grant permissions through the Health Connect dialog. Cannot be bypassed via ADB or `pm grant`.

After granting: tap Refresh. Logcat should show `POST /ingest status=202` with non-empty observations.

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

### 2026-06-06: Session (current)

- [x] GET /observations/recent endpoint added
- [x] DashboardViewModel.refresh() now POSTs to backend (was read-only)
- [x] READ_HEALTH_DATA_IN_BACKGROUND added to manifest and permission sets
- [ ] HC permissions re-granted on device — **PENDING USER ACTION**

---

## Active Work

### Immediate: Prove Phase 1 Complete

**Action required (user, on device):**
1. Unlock phone
2. Open VigilBridge
3. Tap "Grant Permissions" if shown, allow all including Background
4. If on dashboard, tap "Refresh"

**Verification commands (after tap):**
```powershell
# Logcat — should show status=202 with observations
C:\Users\kaliv\AppData\Local\Android\Sdk\platform-tools\adb.exe -s R5CXB2KE0VF logcat -d -s VigilApiClient:D 2>&1 | Select-String "POST /ingest status"

# DB — should show sleep_start_hour row
curl -s "https://vigilbridge.onrender.com/observations/recent?metric_type=sleep_start_hour&limit=5" -H "X-Api-Key: 0dc8144910936507989abc28e059d7d5"
```

---

## Technical Debt

### High priority (fix before Phase 2)

| ID | File | Issue | Fix |
|----|------|-------|-----|
| BUG-001 | MainActivity.kt | onResume permission recheck missing | Add `onResume()` override with lifecycleScope.launch + getGrantedPermissions() |
| BUG-004 | DashboardViewModel.kt | No error state when all HC queries fail | Add `loadError: String?` to DashboardUiState |
| — | DashboardViewModel.kt | init { refresh() } fires before Activity RESUMED, HC reads fail | Move initial POST to LaunchedEffect or use lifecycle observer |

### Medium priority (fix before Phase 3)

| ID | File | Issue | Fix |
|----|------|-------|-----|
| BUG-006 | HealthRepository.kt | Resting HR unverified on S24 Ultra | Open HC app → verify RestingHeartRate data exists; if not, use HeartRateRecord.BPM_MIN 2am–6am fallback |
| — | HealthRepository.kt | RawDashboard.lastSleep is SleepSessionRecord (HC SDK type in domain model) | Extract SleepSummary data class (startTime, endTime, durationMinutes) |
| — | backend | 16 existing observations all from probe payloads; sleep timing values used UTC not IST | Accept as test data, do not delete; real device rows will use corrected IST values |

### Low priority

| ID | File | Issue | Fix |
|----|------|-------|-----|
| BUG-003 | DashboardScreen.kt | Magic literals 1 and 3 in UnavailableScreen | Replace with HealthConnectClient constants |
| BUG-005 | DashboardScreen.kt | collectAsState vs collectAsStateWithLifecycle | Add lifecycle-runtime-compose dep, swap import |
| BUG-007 | app/build.gradle.kts | versionName = "1.0" | Set versionCode=3, versionName="0.3" |
| — | backend/README.md | GET /observations/recent not documented | Add endpoint docs |

---

## Blockers

| Blocker | Owner | Status |
|---------|-------|--------|
| HC permissions reset by reinstall | User (device action) | Active — must re-grant on device |
| Resting HR data availability unconfirmed (BUG-006) | User (HC app check) | Deferred until Phase 1 complete |

---

## Prioritized Next Tasks

After Phase 1 is proven (HC permissions granted, real row in Postgres):

### P0 — Phase 1 closure
1. **Re-grant HC permissions on device** (user action) — unblocks everything
2. **Verify end-to-end**: logcat shows 202, curl shows sleep_start_hour row with IST-correct value

### P1 — Stability before Phase 2
3. **Fix BUG-001**: Add `onResume()` permission recheck — prevents silent state stale after Settings grant
4. **Fix init timing**: Move initial POST call to after Activity RESUMED (prevents WorkManager-style errors on foreground launch)
5. **Verify BUG-006**: Check if resting HR data exists in HC app; implement fallback if not

### P2 — Data quality
6. **Fix BUG-004**: Add error surface to dashboard — currently shows `—` for all metrics on failure, no user feedback
7. **Verify WorkManager background sync**: `adb shell dumpsys jobscheduler | grep vigil` + DB check after 15min background

### P3 — Cleanup before Phase 2
8. **Extract SleepSummary domain model** — decouple ViewModel from HC SDK type
9. **Dashboard shows cached startup values** — load from Room first, then HC refresh
10. **Fix remaining low-priority bugs** — BUG-003, BUG-005, BUG-007

---

## Future Phases (DO NOT START UNTIL PHASE 1 COMPLETE)

### Phase 2: Trend Analysis
- 7/14/30-day rolling averages per metric
- Personal baseline computation
- Anomaly detection vs baseline
- New `trends` table
- GET /trends/{user_id}?metric=sleep_duration_hours&period=7d

**Gate:** ≥14 days of real device observations in Postgres.

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
| Postgres | Live | Render managed, 16 observations (all probe) |
| Android APK | Installed | Debug build, R5CXB2KE0VF |
| GitHub repo | Current | drdeadpool/VigilBridge, auto-deploy from main |
| Migrations | Applied | 77f7b348bccf (initial schema) |

---

## Version History

| Version | Date | Description |
|---------|------|-------------|
| v0.1 | 2026-06-02 | HC dashboard, corrupt record investigation |
| v0.2 | 2026-06-02 | MVVM refactor, Room, WorkManager |
| v0.3 | 2026-06-03-06 | Backend + network, timezone fix, sleep timing, /observations/recent |
