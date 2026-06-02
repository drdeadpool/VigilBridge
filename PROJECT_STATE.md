# VigilBridge — Project State
Last updated: 2026-06-02. Written for zero-context continuation.

---

## Working Features

| Feature | Status | Notes |
|---|---|---|
| Health Connect SDK initialization | ✅ Working | Uses `HealthConnectClient.getOrCreate(this)` |
| Permission request flow | ✅ Working (partial) | Grant works; auto-transition broken (see Broken) |
| Permission re-check button | ✅ Working | Manual workaround for the auto-transition bug |
| Steps today (aggregate) | ✅ Working | Midnight local → now, `StepsRecord.COUNT_TOTAL` |
| Steps last 7 days (aggregate) | ✅ Working | now-7d → now |
| Steps last 30 days (aggregate) | ✅ Working | now-30d → now |
| Sleep duration | ✅ Working | Most recent session in last 48h, formatted `Xh Ym` |
| Sleep bedtime (start) | ✅ Working | Formatted `EEE h:mm a` |
| Sleep wake time (end) | ✅ Working | Formatted `h:mm a` |
| Resting heart rate | ✅ Implemented, unverified | `RestingHeartRateRecord.BPM_AVG` 7-day aggregate. Not confirmed working on device yet — depends on whether Samsung Health writes `RestingHeartRateRecord` to Health Connect |
| Last sync timestamp | ✅ Working | `Instant.now()` stamped after load, shown at bottom |
| Dashboard auto-load | ✅ Working | `DashboardViewModel.init { refresh() }` triggers on first composition |
| Refresh button | ✅ Working | Calls `vm.refresh()`, disabled during load |
| Loading indicator | ✅ Working | `LinearProgressIndicator` shown during `isLoading = true` |
| Error resilience | ✅ Working | Each query individually wrapped; failure shows `—`, no crash |
| UnavailableScreen | ✅ Working | Shown when HC SDK not present or needs update |
| PermissionScreen | ✅ Working | Shown when permissions not granted |
| Clean build | ✅ Verified | `BUILD SUCCESSFUL` on `assembleDebug` |
| Physical device | ✅ Confirmed | Runs on Samsung Galaxy S24 Ultra |

---

## Broken Features

### BROKEN-1: Permission Gate Does Not Auto-Transition

**Symptom:** After tapping "Grant Permissions" and granting all permissions in the system dialog, the app stays on `PermissionScreen`. Dashboard does not appear automatically.

**User impact:** Must tap "Re-check Permissions" manually every launch until fixed.

**Root cause:** `permissionsGranted` is Compose state inside `setContent {}`. The `requestPermissionsLauncher` callback is registered at Activity level and cannot update Compose state directly without a bridge.

**Workaround:** "Re-check Permissions" button works correctly.

---

### BROKEN-2: UnavailableScreen Uses Magic Integer Literals

**Symptom:** Not a runtime crash, but `UnavailableScreen` uses `1` and `3` for `SDK_UNAVAILABLE` and `SDK_UNAVAILABLE_PROVIDER_UPDATE_REQUIRED` instead of the actual constants from `HealthConnectClient`.

**Risk:** If Jetpack updates the constant values (unlikely but possible), the wrong message shows.

---

### BROKEN-3: No onResume Permission Recheck

**Symptom:** If the user grants permissions via Android Settings → App permissions while the app is backgrounded, `permissionsGranted` is stale when they return to the app. No automatic recovery.

---

## Exact App Behavior Right Now

### Flow on first launch (no permissions):
1. Splash → `MainActivity.onCreate()`
2. HC SDK check passes → `HealthConnectClient` created
3. `LaunchedEffect(Unit)` queries `getGrantedPermissions()`
4. Returns empty set → `permissionsGranted = false`
5. Renders `PermissionScreen`:
   - Title: "Vigil"
   - Subtitle: "Health Connect access required"
   - Button: "Grant Permissions"
   - Button: "Re-check Permissions"

### Permission grant flow:
1. Tap "Grant Permissions"
2. System Health Connect permission dialog appears
3. User grants Steps, Sleep, Resting Heart Rate
4. Dialog closes → app returns to `PermissionScreen` (BUG)
5. User taps "Re-check Permissions"
6. `getGrantedPermissions()` called → all 3 in set → `permissionsGranted = true`
7. `VigilScreen` re-renders → creates `HealthRepository` + `DashboardViewModel`
8. `DashboardViewModel.init { refresh() }` fires immediately
9. Dashboard shown with `LinearProgressIndicator`
10. 5 concurrent HC queries execute
11. Results mapped to `DashboardUiState`
12. Dashboard renders with all metric cards and sync timestamp

### Dashboard layout (top to bottom):
```
Vigil                           [Refresh]
━━━━━━━━━━━━━━━━━━━━━━━━━━━ (loading bar, hidden when done)

Steps
┌─────────────────────────────┐
│ TODAY                        │
│ 8,432                        │
└─────────────────────────────┘
┌─────────────────────────────┐
│ LAST 7 DAYS                  │
│ 54,210                       │
└─────────────────────────────┘
┌─────────────────────────────┐
│ LAST 30 DAYS                 │
│ 231,847                      │
└─────────────────────────────┘

Sleep
┌─────────────────────────────┐
│ DURATION                     │
│ 7h 23m                       │
└─────────────────────────────┘
┌─────────────────────────────┐
│ BEDTIME                      │
│ Thu 11:14 PM                 │
└─────────────────────────────┘
┌─────────────────────────────┐
│ WAKE TIME                    │
│ 6:37 AM                      │
└─────────────────────────────┘

Heart
┌─────────────────────────────┐
│ RESTING HEART RATE           │
│ 58 bpm                       │
└─────────────────────────────┘

Synced Jun 2, 11:43 PM
```

Any failed query shows `—` in the card. No error message or indication of why.

---

## Architecture Overview

```
MainActivity (Activity)
├── Creates HealthConnectClient once in onCreate()
├── Holds requestPermissionsLauncher (Activity-level)
├── Checks initial permissions in LaunchedEffect(Unit)
├── Owns permissionsGranted: MutableState<Boolean>
└── setContent → VigilScreen(client, permissionsGranted, ...)

VigilScreen (Composable, DashboardScreen.kt)
├── if !permissionsGranted → PermissionScreen
└── if permissionsGranted
    ├── remember { HealthRepository(client) }
    ├── viewModel { DashboardViewModel(repo) }  ← ViewModel factory
    ├── collectAsState() on vm.state
    └── Dashboard(state, onRefresh)

DashboardViewModel (ViewModel, ui/DashboardViewModel.kt)
├── _state: MutableStateFlow<DashboardUiState>
├── init { refresh() }
├── refresh() → viewModelScope.launch { repo.load() → toUiState() }
└── toUiState() → maps RawDashboard to formatted DashboardUiState strings

HealthRepository (data/HealthRepository.kt)
├── load() → RawDashboard (calls all 4 queries)
├── aggregateSteps(TimeRangeFilter) → Long?
├── readLastSleep(Instant) → SleepSessionRecord?
└── readRestingHR(Instant) → Long?
```

**Pattern:** MVVM. No Hilt/DI — manual factory pattern. Repository returns HC SDK types (not yet domain-modeled). ViewModel formats data for display.

---

## Dependencies and Versions

### Health Connect
```toml
healthConnect = "1.1.0-rc01"
```
```kotlin
implementation("androidx.health.connect:connect-client:1.1.0-rc01")
```

### Lifecycle / ViewModel
```toml
lifecycleRuntimeKtx = "2.10.0"
lifecycleViewmodel = "2.10.0"
```
```kotlin
implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.10.0")
implementation("androidx.lifecycle:lifecycle-viewmodel-ktx:2.10.0")
implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.10.0")
```

### Compose
```toml
composeBom = "2026.02.01"
activityCompose = "1.13.0"
```
```kotlin
implementation(platform("androidx.compose:compose-bom:2026.02.01"))
implementation("androidx.activity:activity-compose:1.13.0")
implementation("androidx.compose.material3:material3")
implementation("androidx.compose.ui:ui")
implementation("androidx.compose.ui:ui-graphics")
```

### Coroutines
```kotlin
implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.10.2")
```

### Core
```toml
coreKtx = "1.18.0"
kotlin = "2.2.10"
agp = "9.2.1"
```

### Min/Target SDK
- `minSdk = 28` (Android 9, required for Health Connect)
- `targetSdk = 36`
- `compileSdk = 36.1` (using `release(36) { minorApiLevel = 1 }` syntax)

### `versionName` = `"1.0"` — **should be updated to `"0.2"`**

---

## File Tree With Responsibilities

```
VigilBridge/
├── HANDOVER.md                          ← Detailed session handover (from this session)
├── PROJECT_STATE.md                     ← This file
├── NEXT_10_STEPS.md                     ← Prioritized task list
├── BUGS.md                              ← Bug registry
├── VIGIL_ROADMAP.md                     ← Version roadmap
├── PROMPTS.md                           ← Continuation prompts for new sessions
├── CODE_REVIEW.md                       ← Technical debt register
├── LESSONS_LEARNED.md                   ← Session learnings
│
├── gradle/
│   ├── libs.versions.toml               ← Version catalog (single source of truth for deps)
│   └── wrapper/gradle-wrapper.properties
│
└── app/
    ├── build.gradle.kts                 ← App-level build: deps, compileSdk, minSdk, versionName
    ├── proguard-rules.pro               ← Empty (minification disabled)
    └── src/main/
        ├── AndroidManifest.xml          ← Package, permissions, HC intent filter
        └── java/com/batman/vigilbridge/
            │
            ├── MainActivity.kt
            │   Responsibilities:
            │   - Activity lifecycle entry point
            │   - HealthConnectClient creation (once, in onCreate)
            │   - Permission launcher registration (Activity-level)
            │   - Initial permission check (LaunchedEffect)
            │   - permissionsGranted state ownership
            │   - Routes to UnavailableScreen or VigilScreen
            │
            ├── data/
            │   └── HealthRepository.kt
            │       Responsibilities:
            │       - All Health Connect query logic
            │       - RawDashboard data class (output model)
            │       - aggregateSteps(filter) → Long?
            │       - readLastSleep(now) → SleepSessionRecord?
            │       - readRestingHR(now) → Long?
            │       - load() → RawDashboard (calls all queries)
            │       - Error handling per-query (returns null on failure)
            │
            └── ui/
                ├── DashboardViewModel.kt
                │   Responsibilities:
                │   - DashboardUiState data class (all String fields)
                │   - DashboardViewModel: StateFlow, viewModelScope, init, refresh()
                │   - toUiState() extension: RawDashboard → DashboardUiState
                │   - All date/number formatting
                │   - ViewModelProvider.Factory companion
                │
                ├── DashboardScreen.kt
                │   Responsibilities:
                │   - UnavailableScreen composable
                │   - VigilScreen composable (top-level, creates repo+vm)
                │   - PermissionScreen composable
                │   - Dashboard composable (layout)
                │   - SectionLabel composable
                │   - MetricCard composable
                │
                └── theme/
                    ├── Color.kt         ← Material3 color scheme (default, unchanged)
                    ├── Theme.kt         ← VigilBridgeTheme wrapper (default, unchanged)
                    └── Type.kt          ← Typography (default, unchanged)
```
