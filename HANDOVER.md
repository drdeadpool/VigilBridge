# VigilBridge v0.2 — Session Handover Document

Generated at end of session. Written for a new Claude context with zero prior chat history.

---

## 1. Project Purpose

**VigilBridge** is an Android app that reads physiological data from Health Connect and displays it as a clean dashboard. It is the data-reading foundation for a larger project called **Vigil** — a physiological intelligence platform for medical professionals (Phase 4 of the BatmanOS roadmap). The app is a standalone diagnostic/prototype, not yet wired to any backend, agent, or sync infrastructure.

The app runs on a physical **Samsung Galaxy S24 Ultra**.

---

## 2. Current Architecture

```
Activity (MainActivity)
  └─ creates HealthConnectClient
  └─ holds permission launcher (registerForActivityResult)
  └─ checks initial permissions (LaunchedEffect)
  └─ passes permissionsGranted + client to VigilScreen

VigilScreen (DashboardScreen.kt)
  └─ if !permissionsGranted → PermissionScreen
  └─ if permissionsGranted  → creates HealthRepository(client)
                            → creates DashboardViewModel via factory
                            → collects DashboardUiState
                            → renders Dashboard composable

DashboardViewModel (ui/DashboardViewModel.kt)
  └─ holds MutableStateFlow<DashboardUiState>
  └─ calls repo.load() on init and on refresh()
  └─ maps RawDashboard → DashboardUiState (formatting happens here)

HealthRepository (data/HealthRepository.kt)
  └─ aggregateSteps(filter) → Long?
  └─ readLastSleep(now)     → SleepSessionRecord?
  └─ readRestingHR(now)     → Long?
  └─ load()                 → RawDashboard
```

**Pattern:** MVVM with manual (no Hilt) dependency injection. Repository returns raw HC SDK types. ViewModel converts to display strings.

---

## 3. File Tree and Responsibilities

```
VigilBridge/
├── gradle/
│   └── libs.versions.toml               ← dependency versions catalog
├── app/
│   ├── build.gradle.kts                 ← app-level build config + dependencies
│   └── src/main/
│       ├── AndroidManifest.xml          ← Health Connect intent filter (unchanged)
│       └── java/com/batman/vigilbridge/
│           ├── MainActivity.kt          ← Activity shell, HC client, permission launcher
│           ├── data/
│           │   └── HealthRepository.kt  ← all Health Connect queries, RawDashboard model
│           └── ui/
│               ├── DashboardScreen.kt   ← all Composables: VigilScreen, Dashboard,
│               │                           PermissionScreen, MetricCard, SectionLabel,
│               │                           UnavailableScreen
│               ├── DashboardViewModel.kt← DashboardUiState data class, ViewModel,
│               │                           companion factory, RawDashboard→UiState mapping
│               └── theme/
│                   ├── Color.kt         ← unchanged
│                   ├── Theme.kt         ← unchanged
│                   └── Type.kt          ← unchanged
```

---

## 4. All Files Modified This Session

### Modified:

| File | Change |
|---|---|
| `gradle/libs.versions.toml` | Added `healthConnect = "1.1.0-rc01"` (was alpha12), added `lifecycleViewmodel = "2.10.0"`, added `lifecycle-viewmodel-ktx` and `lifecycle-viewmodel-compose` library entries |
| `app/build.gradle.kts` | Added `implementation(libs.androidx.lifecycle.viewmodel.ktx)` and `implementation(libs.androidx.lifecycle.viewmodel.compose)` |
| `MainActivity.kt` | Full rewrite: now a thin Activity shell. Removed all HC query code, all diagnostic/scanning code, all state. Imports `UnavailableScreen` and `VigilScreen` from `ui` package. Added `RestingHeartRateRecord` to PERMISSIONS. |

### Created:

| File | Contents |
|---|---|
| `data/HealthRepository.kt` | New file. `RawDashboard` data class + `HealthRepository` class with `load()`, `aggregateSteps()`, `readLastSleep()`, `readRestingHR()` |
| `ui/DashboardViewModel.kt` | New file. `DashboardUiState` data class + `DashboardViewModel` with `StateFlow`, `refresh()`, `toUiState()` extension, companion `factory()` |
| `ui/DashboardScreen.kt` | New file. All Composables: `UnavailableScreen`, `VigilScreen`, `PermissionScreen`, `Dashboard`, `SectionLabel`, `MetricCard` |

### Deleted (implicitly, by full rewrite):

The old single-file `MainActivity.kt` previously contained all composables, all HC logic, all diagnostic scanning buttons, all isolation tools, and the `DashboardData` data class. That is now gone and replaced by the four files above.

---

## 5. Health Connect SDK Version

**Current:** `androidx.health.connect:connect-client:1.1.0-rc01`

**Previous:** `1.1.0-alpha12`

**Reason for upgrade:** alpha12 had a deserialization bug in `RecordConvertersKt.toSdkStepsRecord()` — it threw `IllegalArgumentException: startTime must be before endTime` when deserializing a specific corrupt `StepsRecord` stored in Health Connect's database on the device. RC01 was the stable candidate at the time of upgrade.

**Maven location for latest version:** `https://maven.google.com/web/index.html#androidx.health.connect:connect-client`

---

## 6. Known Bugs

### BUG-1: Corrupt StepsRecord in Health Connect database (BYPASSED, NOT FIXED)

**Description:** A `StepsRecord` exists in the device's Health Connect database with `startTime >= endTime`. This is corrupt data stored on-device by another app (likely Samsung Health or a fitness tracker).

**Isolation evidence:**
- All 1h, 24h, 3d, 4d, 4.25d windows: OK
- 4.50d window: FAIL
- Page-by-page scan of the 4.25d–4.50d window identified the last good record:
  - `startTime = 2026-05-29T08:53:09.444Z`
  - `endTime   = 2026-05-29T08:53:23.444Z`
  - `count     = 7`
  - The next record in sequence throws `IllegalArgumentException: startTime must be before endTime`

**Status:** BYPASSED. App no longer calls `readRecords(StepsRecord)` anywhere. Step counts are read exclusively via `client.aggregate(AggregateRequest(metrics = setOf(StepsRecord.COUNT_TOTAL), ...))` which does not deserialize individual records and is unaffected by the corrupt entry.

**Cannot fix:** The corrupt record lives in Health Connect's own database. It can only be deleted via the Health Connect app UI (Settings → Data & access → StepsRecord → delete), not via API.

---

## 7. Current Blocker: Permission Gate Does Not Auto-Transition

**Symptom:** After the user taps "Grant Permissions" and grants Health Connect permissions in the system dialog, the app stays on the `PermissionScreen`. The dashboard does not appear automatically. The user must tap "Re-check Permissions" to trigger the state update and see the dashboard.

**Root cause:**

In `MainActivity.kt`, `permissionsGranted` is a Compose `var` managed inside `setContent {}`:

```kotlin
var permissionsGranted by remember { mutableStateOf(false) }

LaunchedEffect(Unit) {
    val granted = client.permissionController.getGrantedPermissions()
    permissionsGranted = PERMISSIONS.all { it in granted }
}
```

The `requestPermissionsLauncher` callback (registered at Activity level via `registerForActivityResult`) only logs:

```kotlin
private val requestPermissionsLauncher = registerForActivityResult(
    PermissionController.createRequestPermissionResultContract()
) { granted ->
    Log.d(TAG, "Permissions granted: $granted")
    // does NOT update permissionsGranted state
}
```

Because `permissionsGranted` is a Compose state inside `setContent`, it is not accessible from the Activity-level launcher callback.

**Fix (not yet applied):**

Option A — Re-check inside launcher callback using a shared `MutableState` hoisted to Activity scope:

```kotlin
// In MainActivity fields:
private val permissionsGranted = mutableStateOf(false)

// In launcher:
private val requestPermissionsLauncher = registerForActivityResult(
    PermissionController.createRequestPermissionResultContract()
) { _ ->
    lifecycleScope.launch {
        val granted = healthConnectClient?.permissionController?.getGrantedPermissions()
        permissionsGranted.value = granted != null && PERMISSIONS.all { it in granted }
    }
}

// In setContent:
val permissionsGranted by this.permissionsGranted  // read the Activity-level state
```

Option B — Move permission launcher into a Composable using `rememberLauncherForActivityResult`. This is the idiomatic Compose approach but requires the launcher to be inside the Composable tree, not Activity-level.

Option C — Use `OnResumeEffect` or `DisposableEffect(lifecycle)` to re-check permissions when the Activity resumes after the system permission dialog closes.

**Recommended fix:** Option A is the least disruptive change. Option B is the most idiomatic but requires moving the launcher.

---

## 8. What Worked Before the v0.2 Refactor (v0.1 state)

At end of v0.1, the app was a single `MainActivity.kt` with everything inline:

- `DashboardData` data class (steps today/7d/30d, sleep duration/window as formatted strings)
- `loadDashboard()` suspend function called from `LaunchedEffect`
- `aggregateSteps()` and `readLastSleep()` as top-level suspend functions
- Auto-load on `permissionsGranted` becoming true
- Refresh via incrementing `refreshTrigger` integer state
- No ViewModel, no repository
- `MetricCard` composable, section labels, clean dashboard layout
- `PermissionScreen` shown when not granted
- Steps displayed with commas, sleep with `h m` duration

Steps aggregate worked correctly (bypassing corrupt StepsRecord).
Sleep read worked correctly.
No resting heart rate.
No last sync timestamp.

---

## 9. What Changed During v0.2

1. **Architecture:** Extracted from single-file to `MainActivity` + `data/HealthRepository` + `ui/DashboardViewModel` + `ui/DashboardScreen`.

2. **DashboardViewModel:** Added `StateFlow<DashboardUiState>`, `viewModelScope.launch`, `init { refresh() }`. ViewModel survives recomposition and configuration changes.

3. **HealthRepository:** Extracted all HC queries. Added `RawDashboard` data class. Added `readRestingHR()` calling `RestingHeartRateRecord.BPM_AVG` aggregate.

4. **New permissions:** Added `HealthPermission.getReadPermission(RestingHeartRateRecord::class)` to the `PERMISSIONS` set. Users who already granted v0.1 permissions will be prompted again for `RestingHeartRateRecord` permission.

5. **New data:** Resting heart rate (7-day BPM_AVG aggregate). Last sync timestamp (formatted `Instant.now()` at end of load).

6. **Sleep detail:** v0.1 showed sleep as one card (duration + window combined). v0.2 shows three cards: Duration, Bedtime, Wake time.

7. **SDK:** Upgraded from alpha12 to rc01.

8. **Dependencies:** Added `lifecycle-viewmodel-ktx:2.10.0` and `lifecycle-viewmodel-compose:2.10.0` explicitly to `build.gradle.kts`.

9. **Formatting:** ViewModel's `toUiState()` extension function does all date/number formatting. UI layer receives only `String` values.

10. **`UnavailableScreen`:** Moved from `MainActivity.kt` to `ui/DashboardScreen.kt`. Uses integer literals for SDK status codes (1 = SDK_UNAVAILABLE, 3 = SDK_UNAVAILABLE_PROVIDER_UPDATE_REQUIRED) because importing `HealthConnectClient` constants into the UI file was avoided to keep the UI layer HC-agnostic. **NOTE:** This is fragile — see TODOs.

---

## 10. Exact Current App Behavior

### On launch:
1. Activity checks `HealthConnectClient.getSdkStatus(this)`.
2. If SDK unavailable → shows `UnavailableScreen` with error message.
3. If SDK available → creates `HealthConnectClient`, calls `getGrantedPermissions()`.
4. If all three permissions not granted → shows `PermissionScreen` with "Grant Permissions" and "Re-check Permissions" buttons.
5. If permissions granted → `VigilScreen` creates `HealthRepository(client)`, creates `DashboardViewModel` via factory, calls `repo.load()` automatically (in `init`).

### Permission screen:
- "Grant Permissions" launches system Health Connect permission dialog.
- After dialog closes, app **stays on PermissionScreen** (blocker — see section 7).
- "Re-check Permissions" manually re-queries `getGrantedPermissions()` and updates `permissionsGranted`. If now true, transitions to Dashboard.

### Dashboard screen:
- Shows `LinearProgressIndicator` while loading.
- "Refresh" button disabled during load.
- Loads 5 HC queries concurrently within `repo.load()`:
  - Steps today (midnight → now)
  - Steps 7d (now-7d → now)
  - Steps 30d (now-30d → now)
  - Last sleep session (now-48h → now, pageSize=1, ascending=false)
  - Resting HR avg (now-7d → now, BPM_AVG aggregate)
- Any query failure shows `—` for that metric (no crash).
- Sleep: last session within 48 hours. If no sleep in 48h, shows `—` for all sleep cards.
- Resting HR: 7-day average. Returns `—` if no resting HR data recorded.
- After load: shows sync timestamp `"Synced MMM d, h:mm a"`.

### Cards displayed:
```
Steps
  TODAY          [number with commas or —]
  LAST 7 DAYS    [number with commas or —]
  LAST 30 DAYS   [number with commas or —]

Sleep
  DURATION       [Xh Ym or —]
  BEDTIME        [EEE h:mm a or —]
  WAKE TIME      [h:mm a or —]

Heart
  RESTING HEART RATE  [X bpm or —]

Synced MMM d, h:mm a
```

---

## 11. TODOs

### HIGH PRIORITY

- **TODO-1:** Fix permission gate auto-transition (see section 7). Use Option A (hoist `permissionsGranted` to Activity field) or Option B (move launcher to Composable).

- **TODO-2:** Replace integer literals in `UnavailableScreen` with actual constants. Currently uses `1` and `3` for `SDK_UNAVAILABLE` and `SDK_UNAVAILABLE_PROVIDER_UPDATE_REQUIRED`. Should import from `HealthConnectClient` or pass the resolved string from `MainActivity`. Using raw integers is fragile.

- **TODO-3:** Re-grant check after returning from permission dialog. If user goes to system Settings → grants permission manually → returns to app, `permissionsGranted` will be stale. Need `onResume`-triggered recheck.

### MEDIUM PRIORITY

- **TODO-4:** The `versionName` in `build.gradle.kts` is still `"1.0"`. Update to `"0.2"` to match actual version.

- **TODO-5:** Sleep query uses a hardcoded 48h lookback. If user hasn't slept in 48h (e.g., long travel), no sleep data shows. Consider expanding to 72h or making configurable.

- **TODO-6:** `minSdk = 28`. Health Connect requires Android 9 (API 28) minimum. This is correct but worth documenting explicitly as a constraint.

- **TODO-7:** `isMinifyEnabled = false` in release build config. Enable minification before any release build.

- **TODO-8:** Steps aggregate for "today" uses `LocalDate.now(zone).atStartOfDay(zone).toInstant()`. If user is in a timezone that changed (daylight saving transition), this is still correct. But worth noting this is locale/timezone-dependent.

### LOW PRIORITY

- **TODO-9:** No unit tests exist. The `HealthRepository` is testable with a fake `HealthConnectClient`. `DashboardViewModel.toUiState()` is a pure function and easily testable.

- **TODO-10:** `SleepSessionRecord` is returned directly from `HealthRepository` to `DashboardViewModel`. This couples the ViewModel to the HC SDK. Future refactor: define a `SleepSummary` domain model in the `data` package and convert in the repository.

- **TODO-11:** No error state surfaced to UI. If all queries fail (e.g., HC service down), the dashboard shows all `—` with no explanation. Add an error banner or retry mechanism.

- **TODO-12:** `RestingHeartRateRecord` permission was added in v0.2. Existing installs from v0.1 will not have this permission granted. The permission screen will re-appear. This is expected but worth noting.

---

## 12. Assumptions Made During This Session

1. **Corrupt StepsRecord origin:** Assumed the corrupt record was written by Samsung Health or a third-party fitness app — not by VigilBridge itself (VigilBridge only reads, never writes). VigilBridge has never called `insertRecords()`.

2. **BPM_AVG for resting HR:** Used `RestingHeartRateRecord.BPM_AVG` over 7 days. Assumed the device has some resting HR data. If Samsung Health records `RestingHeartRateRecord` entries (which it does on S24 Ultra), this will return a value. If not, returns `—` gracefully.

3. **`collectAsState()` vs `collectAsStateWithLifecycle()`:** Used `collectAsState()` in `DashboardScreen.kt` to avoid adding the `lifecycle-runtime-compose` dependency. This means the StateFlow is collected even when the app is in the background. For this use case (no continuous data streams), this is acceptable.

4. **ViewModel factory approach:** Used `viewModelFactory { initializer { ... } }` from `lifecycle-viewmodel-ktx`. Assumed this is available transitively or via the explicitly added `lifecycle-viewmodel-ktx:2.10.0` dependency.

5. **`pageToken` (not `nextPageToken`):** During the pagination debugging, discovered via `javap` on the rc01 JAR that `ReadRecordsResponse` exposes `getPageToken()` (Kotlin property: `pageToken`), NOT `nextPageToken`. This was verified directly from the bytecode — do not assume field names from documentation without verification.

6. **RC01 stable enough:** Upgraded to `1.1.0-rc01` from `alpha12`. Assumed RC is production-stable for this prototype. If a newer stable (`1.1.0` or `1.2.x`) has been released since, consider upgrading.

7. **Sleep session detection:** Using `ascendingOrder = false, pageSize = 1` to get the most recent sleep session. Assumes the most recently ended session is "last night's sleep." Does not account for naps or unusual sleep patterns.

8. **Resting HR time window:** Used 7 days for resting HR average. Assumed this gives a representative reading. Could narrow to 1–3 days for more current data if the device records resting HR daily.

---

## 13. Next Recommended Steps (Priority Order)

### Step 1 — Fix permission auto-transition (BLOCKER)
The app requires manual "Re-check" tap after granting permissions. Fix by hoisting `permissionsGranted` to Activity-level `MutableState` and re-checking inside the `requestPermissionsLauncher` callback via `lifecycleScope.launch`. This is a one-file change to `MainActivity.kt`.

```kotlin
// In MainActivity (pseudocode for the fix):
private val permGranted = mutableStateOf(false)

private val requestPermissionsLauncher = registerForActivityResult(...) { _ ->
    lifecycleScope.launch {
        val g = healthConnectClient?.permissionController?.getGrantedPermissions()
        permGranted.value = g != null && PERMISSIONS.all { it in g }
    }
}
// In setContent: val permissionsGranted by permGranted
```

### Step 2 — Fix UnavailableScreen SDK status constants
Replace integer literals `1` and `3` in `UnavailableScreen` with proper constants. Either import `HealthConnectClient` in the UI file, or pass a resolved error string from `MainActivity`.

### Step 3 — Add onResume permission recheck
In `MainActivity`, add a lifecycle observer or `LaunchedEffect(lifecycle)` to re-check permissions when the Activity resumes. This handles the case where the user grants permissions via Android Settings while the app is backgrounded.

### Step 4 — Update `versionName` to `"0.2"`
One-line change in `app/build.gradle.kts`.

### Step 5 — Verify resting HR data on device
Run the app and confirm the "Resting heart rate" card shows a value. If it shows `—`, either (a) Samsung Health is not recording `RestingHeartRateRecord` to Health Connect, or (b) the `RestingHeartRateRecord` permission was not granted. Check via Health Connect app → Data & access.

### Step 6 — Verify new permission prompt appears
Since `RestingHeartRateRecord` permission was added in v0.2, existing installs will see the permission screen again. Confirm the grant flow works and all three permissions are granted before dashboard loads.

### Step 7 — Extract SleepSummary domain model
Create `data/SleepSummary.kt`:
```kotlin
data class SleepSummary(
    val startTime: Instant,
    val endTime: Instant,
    val durationMinutes: Long,
)
```
Convert in `HealthRepository.readLastSleep()`. Removes HC SDK type dependency from `DashboardViewModel`.

### Step 8 — Add error state to UiState
Add `val error: String?` to `DashboardUiState`. If `repo.load()` throws entirely (not per-metric), surface a user-visible message. Currently all-failure mode shows silent `—` for everything.

### Step 9 — Enable release minification
Set `isMinifyEnabled = true` in release build type. Test that Health Connect classes are not stripped (may need ProGuard rules for reflection-based record types).

### Step 10 — Expand to Phase 2 Vigil metrics
Once the above are stable, the next physiological metrics to add from Health Connect:
- `SpO2Record` (blood oxygen) — `OxygenSaturationRecord.PERCENTAGE_AVG`
- `RespiratoryRateRecord` — `RespiratoryRateRecord.RATE_AVG`
- `BloodPressureRecord` — systolic/diastolic averages
- `BodyTemperatureRecord`
All follow the same `AggregateRequest` pattern already established.

---

## 14. How to Verify the Build

```bash
# From repo root, requires Android Studio JBR on PATH:
export JAVA_HOME="/c/Program Files/Android/Android Studio/jbr"
cd AndroidStudioProjects/VigilBridge
./gradlew assembleDebug

# Install on connected device:
./gradlew installDebug
```

Last successful build: `BUILD SUCCESSFUL in 31s` (36 tasks, 9 executed, 27 up-to-date).

---

## 15. Project File Locations

- Project root: `C:\Users\kaliv\AndroidStudioProjects\VigilBridge\`
- Main source: `app\src\main\java\com\batman\vigilbridge\`
- Gradle catalog: `gradle\libs.versions.toml`
- App build file: `app\build.gradle.kts`
- This handover doc: `HANDOVER.md` (project root)

---

*End of handover document. Last updated: 2026-06-02.*
