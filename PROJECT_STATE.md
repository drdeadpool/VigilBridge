# VigilBridge — Project State
Last updated: 2026-06-06. Written for zero-context continuation.

---

## Working Features

| Feature | Status | Notes |
|---|---|---|
| Health Connect SDK initialization | ✅ Working | `HealthConnectClient.getOrCreate(this)` |
| Permission request flow | ✅ Fixed | `rememberLauncherForActivityResult` — auto-transitions on grant |
| Permission re-check button | ✅ Working | Manual fallback |
| Steps today (aggregate) | ✅ Working | Midnight local → now, `StepsRecord.COUNT_TOTAL` |
| Steps last 7 days | ✅ Working | now-7d → now |
| Steps last 30 days | ✅ Working | now-30d → now |
| Sleep duration | ✅ Working | Most recent session in last 48h, formatted `Xh Ym` |
| Sleep bedtime (start) | ✅ Working | Formatted `EEE h:mm a` |
| Sleep wake time (end) | ✅ Working | Formatted `h:mm a` |
| Resting heart rate | ✅ Implemented, unverified on device | `RestingHeartRateRecord.BPM_AVG` 7-day. Samsung Health must write resting HR to HC. |
| Last sync timestamp | ✅ Working | `Instant.now()` after each load |
| Dashboard auto-load | ✅ Working | `DashboardViewModel.init { refresh() }` |
| Refresh button | ✅ Working | Disabled during load |
| Loading indicator | ✅ Working | `LinearProgressIndicator` |
| Error resilience | ✅ Working | Per-query catch; failure → `—`, no crash |
| UnavailableScreen | ✅ Working | Shown when HC SDK not present or needs update |
| PermissionScreen | ✅ Working | Shown when permissions not granted |
| Room database | ✅ Working | `VitalsSnapshot` written after every HC load |
| Background sync | ✅ Proven | WorkManager fires autonomously every 15 min when connected. `NetworkType.CONNECTED` constraint required. POST /ingest status=202 confirmed without user interaction. DB 40→56 verified. |
| Clean build | ✅ Verified | `BUILD SUCCESSFUL` — 37 tasks |
| Physical device | ✅ Confirmed | Samsung Galaxy S24 Ultra |

---

## Broken Features

### None blocking data collection.

### Known open issues:
- **BUG-001:** onResume permission recheck missing. Fix before Phase 2 implementation.
- **BUG-003:** `UnavailableScreen` magic literals. Low risk; fix when touching that file.
- **BUG-004:** No error surface when HC queries fail. Fix before Phase 2.
- **BUG-006:** Resting HR deferred to Phase 2. Will use `HeartRateRecord.BPM_MIN` (02:00–06:00) fallback.
- **Sleep model discrepancy:** Samsung Health shows 5h 42m actual sleep; Vigil captured 4h 33m (same session). Must investigate `SleepSessionRecord` stages before Phase 2 trend computation.

---

## Architecture Overview

```
MainActivity (Activity)
├── getSdkStatus → creates HealthConnectClient
├── VitalsSyncWorker.schedule(this)          ← schedules 15-min background job
├── rememberLauncherForActivityResult        ← permission launcher (Compose scope)
├── LaunchedEffect(Unit)                     ← initial permission check
├── permissionsGranted: MutableState<Boolean>
└── setContent → VigilScreen(client, permissionsGranted, ...)

VigilScreen (Composable, ui/DashboardScreen.kt)
├── if !permissionsGranted → PermissionScreen
└── if permissionsGranted
    ├── LocalContext → VigilDatabase.get() → VitalsDao
    ├── remember { HealthRepository(client, dao) }
    ├── viewModel { DashboardViewModel(repo) }
    ├── collectAsState() on vm.state
    └── Dashboard(state, onRefresh)

DashboardViewModel (ui/DashboardViewModel.kt)
├── MutableStateFlow<DashboardUiState>
├── init { refresh() }
└── refresh() → viewModelScope → repo.load() → toUiState()

HealthRepository (data/HealthRepository.kt)
├── load() → RawDashboard + dao.insert(toSnapshot())
├── aggregateSteps(filter) → Long?
├── readLastSleep(now) → SleepSessionRecord?
└── readRestingHR(now) → Long?

VigilDatabase (data/VigilDatabase.kt)
└── singleton Room DB → vitals_snapshots table

VitalsSyncWorker (work/VitalsSyncWorker.kt)
├── CoroutineWorker, 15-min periodic, requires NetworkType.CONNECTED
├── Checks HC SDK status
├── Checks permissions still granted (including READ_HEALTH_DATA_IN_BACKGROUND)
├── Creates HealthRepository(client, dao)
├── Calls repo.load() → writes snapshot to Room
└── VigilApiClient.postSnapshot() → POST /ingest (fire-and-forget; failure → success on next cycle)
```

**Pattern:** MVVM. Manual DI (no Hilt). Repository handles all HC queries and Room writes.

---

## Build State

- **Last successful build:** 2026-06-06
- **Build command:** `JAVA_HOME="/c/Program Files/Android/Android Studio/jbr" ./gradlew assembleDebug`
- **Result:** `BUILD SUCCESSFUL in 34s — 37 tasks`
- **Known warning:** `android.disallowKotlinSourceSets=false` — experimental flag required for KSP + AGP 9.x "built-in Kotlin" compatibility. Not a runtime issue.

---

## Dependencies and Versions

| Library | Version | Purpose |
|---|---|---|
| AGP | 9.2.1 | Android build |
| Kotlin | 2.2.10 | Language |
| KSP | 2.2.10-2.0.2 | Room annotation processor |
| Compose BOM | 2026.02.01 | UI |
| activity-compose | 1.13.0 | `setContent`, launchers |
| lifecycle-viewmodel | 2.10.0 | ViewModel + StateFlow |
| health-connect | 1.1.0-rc01 | Data source |
| room-runtime + ktx | 2.7.1 | Local persistence |
| work-runtime-ktx | 2.10.0 | Background sync |
| coroutines-android | 1.10.2 | Async |

- `minSdk = 28` (Android 9)
- `targetSdk = 36`

---

## File Tree With Responsibilities

```
VigilBridge/
├── gradle/libs.versions.toml        ← Single source of truth for all dep versions
├── app/build.gradle.kts             ← App deps; plugins: AGP, kotlin-compose, ksp
├── build.gradle.kts                 ← Root plugin declarations (apply false)
├── gradle.properties                ← android.disallowKotlinSourceSets=false (KSP compat)
│
└── app/src/main/
    ├── AndroidManifest.xml          ← HC permissions (READ_STEPS, READ_SLEEP, READ_HEART_RATE)
    └── java/com/batman/vigilbridge/
        ├── MainActivity.kt          ← Activity entry, HC init, permission launcher, WorkManager schedule
        ├── data/
        │   ├── HealthRepository.kt  ← All HC queries + Room write after each load
        │   ├── RawDashboard         ← (data class inside HealthRepository.kt)
        │   ├── VitalsSnapshot.kt    ← Room entity (vitals_snapshots table)
        │   ├── VitalsDao.kt         ← Room DAO: insert, getLatest, getRecent(n)
        │   └── VigilDatabase.kt     ← Room DB singleton (vigil.db)
        ├── ui/
        │   ├── DashboardScreen.kt   ← All Composables; wires LocalContext→DB→repo
        │   ├── DashboardViewModel.kt← StateFlow<DashboardUiState>, refresh(), toUiState()
        │   └── theme/               ← Unchanged Material3 defaults
        └── work/
            └── VitalsSyncWorker.kt  ← CoroutineWorker, 15-min periodic HC→Room sync
```
