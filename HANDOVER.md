# VigilBridge — Session Handover
Last updated: 2026-06-03. Written for zero-context continuation.

---

## 1. Project Purpose

VigilBridge reads physiological data from Health Connect and displays it as a dashboard. It is the data pipeline foundation for **Vigil** — a physiological intelligence platform for medical professionals (Phase 4 of BatmanOS roadmap). Target device: Samsung Galaxy S24 Ultra.

---

## 2. Current Architecture

```
MainActivity
  └─ HC SDK check → VitalsSyncWorker.schedule(this)
  └─ rememberLauncherForActivityResult (permission grant → updates Compose state)
  └─ LaunchedEffect(Unit) (initial permission check)
  └─ setContent → VigilScreen(client, permissionsGranted, ...)

VigilScreen (DashboardScreen.kt)
  └─ if !permissionsGranted → PermissionScreen
  └─ if permissionsGranted
       └─ LocalContext → VigilDatabase.get() → VitalsDao
       └─ HealthRepository(client, dao)
       └─ DashboardViewModel(repo) via factory
       └─ collectAsState → Dashboard composable

HealthRepository (data/HealthRepository.kt)
  └─ load() → all 5 HC queries → dao.insert(toSnapshot()) → return RawDashboard

VitalsSyncWorker (work/VitalsSyncWorker.kt)
  └─ CoroutineWorker, 15-min periodic via WorkManager
  └─ Checks HC SDK + permissions
  └─ Creates HealthRepository(client, dao) → repo.load() → writes Room
  └─ Result.success() or Result.retry()

VigilDatabase (data/VigilDatabase.kt)
  └─ Room singleton, "vigil.db"
  └─ VitalsSnapshot entity (vitals_snapshots table)
  └─ VitalsDao: insert, getLatest, getRecent(n)
```

**Pattern:** MVVM, manual DI (no Hilt), Repository is HC+Room boundary.

---

## 3. File Inventory

| File | Role |
|---|---|
| `MainActivity.kt` | Activity shell: HC init, permission launcher, WorkManager schedule |
| `data/HealthRepository.kt` | All HC queries + snapshot write to Room |
| `data/VitalsSnapshot.kt` | Room entity — 9 columns (timestamp + all vitals) |
| `data/VitalsDao.kt` | `insert`, `getLatest`, `getRecent(n)` |
| `data/VigilDatabase.kt` | Room singleton `vigil.db`, `exportSchema=false` |
| `ui/DashboardScreen.kt` | All Composables; creates DB+repo via LocalContext |
| `ui/DashboardViewModel.kt` | `StateFlow<DashboardUiState>`, `refresh()`, `toUiState()` |
| `work/VitalsSyncWorker.kt` | Background 15-min HC→Room sync worker |
| `AndroidManifest.xml` | HC permissions: READ_STEPS, READ_SLEEP, READ_HEART_RATE |
| `gradle/libs.versions.toml` | All dep versions (single source of truth) |
| `app/build.gradle.kts` | Plugins: AGP, kotlin-compose, ksp. All deps. |
| `gradle.properties` | `android.disallowKotlinSourceSets=false` (KSP+AGP9 compat) |

---

## 4. Build Instructions

```bash
export JAVA_HOME="/c/Program Files/Android/Android Studio/jbr"
cd AndroidStudioProjects/VigilBridge
./gradlew assembleDebug   # BUILD SUCCESSFUL in ~34s
./gradlew installDebug    # deploy to connected device
```

**Known warning (non-blocking):**
> `android.disallowKotlinSourceSets=false is experimental`
KSP 2.2.10-2.0.2 registers generated sources via `kotlin.sourceSets`, which AGP 9.x "built-in Kotlin" disallows by default. The flag suppresses the error. No runtime impact.

---

## 5. Key Build Issues Resolved This Session

| Error | Root Cause | Fix |
|---|---|---|
| KSP plugin `2.2.10-1.0.33` not found | KSP 2.x changed versioning to `{kotlin}-{ksp2_ver}` | Changed to `2.2.10-2.0.2` |
| `Cannot add extension 'kotlin' — already registered` | AGP 9 built-in Kotlin conflicts with explicit `kotlin-android` plugin | Removed `kotlin-android` from all build files |
| `Using kotlin.sourceSets DSL not allowed` | KSP source registration conflicts with AGP 9 built-in Kotlin | Set `android.disallowKotlinSourceSets=false` in `gradle.properties` |

---

## 6. WorkManager Background Sync Details

- **Worker class:** `VitalsSyncWorker` (`CoroutineWorker`)
- **Work name:** `vigil_vitals_sync` (unique, `KEEP` policy — won't re-schedule if running)
- **Interval:** 15 minutes (WorkManager minimum)
- **Constraints:** None (runs on any network, any battery state)
- **Scheduled from:** `MainActivity.onCreate()` when HC SDK is available
- **Failure handling:** `Result.retry()` on HC query failures; `Result.success()` if SDK unavailable or permissions revoked (no point retrying)
- **Data written:** calls `repo.load()` which writes `VitalsSnapshot` row to Room (same path as foreground refresh)
- **No notifications:** silent background sync

**To verify background sync ran:**
```
Android Studio → App Inspection → WorkManager → vigil_vitals_sync
adb shell dumpsys jobscheduler | grep vigil
Android Studio → App Inspection → Database Inspector → vitals_snapshots
```

---

## 7. Known Open Issues

| ID | Severity | Description |
|---|---|---|
| BUG-003 | Low | `UnavailableScreen` uses `1` and `3` instead of `HealthConnectClient` constants |
| BUG-006 | Medium | Resting HR unverified on S24 Ultra — Samsung Health may not share `RestingHeartRateRecord` to HC |
| TODO | Medium | `onResume` permission recheck missing — grants via Settings while backgrounded won't be detected until next launch |
| TODO | Low | `versionName = "1.0"` — should be `"0.3"` |

---

## 8. Phase 1 Roadmap Status

| Milestone | Status |
|---|---|
| Local HC dashboard | ✅ Done |
| Permission gate fix | ✅ Done |
| Room local persistence | ✅ Done |
| WorkManager background sync | ✅ Done |
| Dashboard shows cached startup values | ⬜ Next |
| SpO2 + respiratory metrics | ⬜ Blocked on device verification |
| Backend sync | ⬜ Phase 2 |

---

## 9. Next Recommended Action

**Before writing more code:** Install current build on S24 Ultra.
1. Verify resting HR card shows a value (not `—`)
2. Wait 15 min backgrounded → check WorkManager ran → verify new Row in `vitals_snapshots`
3. If both confirmed: proceed to Task 9 (cached startup) and Task 7 (SpO2/respiratory)
4. If resting HR shows `—`: implement `HeartRateRecord.BPM_MIN` fallback (2am–6am window)

---

*End of handover. Last build: 2026-06-03, BUILD SUCCESSFUL.*
