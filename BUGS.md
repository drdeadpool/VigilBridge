# VigilBridge — Bug Registry
Last updated: 2026-06-06.

---

## BUG-001: Permission Gate Does Not Auto-Transition After Grant

**Severity:** High — impacts every new install  
**Status:** Open  
**Introduced:** v0.2 refactor  

### Symptom
After tapping "Grant Permissions" and completing the Health Connect system permission dialog, the app returns to `PermissionScreen` instead of transitioning to the dashboard. User must manually tap "Re-check Permissions" to proceed.

### Root Cause
`permissionsGranted` is a `MutableState<Boolean>` declared inside `setContent {}` using `remember { mutableStateOf(false) }`. The `requestPermissionsLauncher` is registered at Activity level via `registerForActivityResult()`. These two live in different scopes. The launcher callback fires on the main thread after the system dialog closes, but it has no reference to the Compose state and cannot update it. The Compose state is only re-read when the user explicitly triggers the "Re-check Permissions" button.

### Evidence
- App remains on `PermissionScreen` after successful permission grant (observed on S24 Ultra)
- "Re-check Permissions" button correctly transitions to dashboard when tapped
- Logcat shows launcher callback fires: `D/MainActivity: Permissions granted: [...]`
- Despite the callback firing, no recomposition occurs

### Code Location
`MainActivity.kt` — inside `setContent {}`:
```kotlin
var permissionsGranted by remember { mutableStateOf(false) }
LaunchedEffect(Unit) {
    val granted = client.permissionController.getGrantedPermissions()
    permissionsGranted = PERMISSIONS.all { it in granted }
}
```
Launcher callback (no state update):
```kotlin
private val requestPermissionsLauncher = registerForActivityResult(
    PermissionController.createRequestPermissionResultContract()
) { granted ->
    Log.d(TAG, "Permissions granted: $granted")
    // NO STATE UPDATE HERE — this is the bug
}
```

### Failed Fixes
None attempted. Bug identified at end of session before fix could be applied.

### Recommended Fix
Hoist `permissionsGranted` to Activity-level `MutableState` so the launcher callback can write to it:

```kotlin
// In MainActivity class body (not inside setContent):
private val permissionsGranted = mutableStateOf(false)

// Updated launcher:
private val requestPermissionsLauncher = registerForActivityResult(
    PermissionController.createRequestPermissionResultContract()
) { _ ->
    lifecycleScope.launch {
        try {
            val granted = healthConnectClient?.permissionController?.getGrantedPermissions()
            permissionsGranted.value = granted != null && PERMISSIONS.all { it in granted }
        } catch (e: Exception) {
            Log.e(TAG, "Post-grant permission recheck failed", e)
        }
    }
}

// In setContent: read the Activity-level state
val pg by permissionsGranted  // composes correctly because MutableState is observable

// Also move initial check from LaunchedEffect to lifecycleScope in onCreate():
lifecycleScope.launch {
    val granted = healthConnectClient?.permissionController?.getGrantedPermissions()
    permissionsGranted.value = granted != null && PERMISSIONS.all { it in granted }
}
```

**Also add `onResume` recheck** for cases where user grants via Settings while app is backgrounded:
```kotlin
override fun onResume() {
    super.onResume()
    lifecycleScope.launch {
        val granted = healthConnectClient?.permissionController?.getGrantedPermissions()
        permissionsGranted.value = granted != null && PERMISSIONS.all { it in granted }
    }
}
```

---

## BUG-002: Corrupt StepsRecord in Health Connect Database

**Severity:** High — crashed the app on every `readRecords(StepsRecord)` call  
**Status:** Bypassed (not fixed at root)  
**Introduced:** Pre-existing corrupted data on the S24 Ultra  

### Symptom
`client.readRecords(ReadRecordsRequest(StepsRecord::class, timeRangeFilter))` threw:
```
java.lang.IllegalArgumentException: startTime must be before endTime
```
The app failed at STEP3 in the original code. `SleepSessionRecord` reads succeeded with the exact same `TimeRangeFilter`, proving the filter was not the cause.

### Root Cause
A `StepsRecord` entry in Health Connect's on-device database has `startTime >= endTime`. This is corrupt data, almost certainly written by Samsung Health or a third-party fitness tracker. When `readRecords()` is called, the Health Connect SDK deserializes all records in the time range into `StepsRecord` Kotlin objects. The `StepsRecord` constructor validates `require(startTime.isBefore(endTime))` and throws on the corrupt entry.

The error message `"startTime must be before endTime"` is misleading — it refers to the stored record's own fields, NOT to the `TimeRangeFilter` passed to `readRecords()`. This caused significant wasted investigation time.

### Evidence
- Stacktrace: exception originates at `StepsRecord.<init>()` via `RecordConvertersKt.toSdkStepsRecord()` — confirmed this is deserialization, not query validation
- `SleepSessionRecord` read with identical filter succeeded — proves filter is valid
- `TimeRangeFilter` logs confirmed `startBeforeEnd=true`, `startEpoch < endEpoch`
- Binary search on time windows:
  - 1h, 24h, 3d, 4d, 4.25d → OK
  - 4.50d, 5d, 6d, 7d → FAIL
- Page-by-page scan (`pageSize=1`, `ascendingOrder=true`) of window `4.50d→4.25d ago`:
  - Last successfully decoded record:
    - `startTime = 2026-05-29T08:53:09.444Z`
    - `endTime   = 2026-05-29T08:53:23.444Z`
    - `count     = 7`
  - Next page threw `IllegalArgumentException: startTime must be before endTime`
  - The corrupt record immediately follows this entry in the database

### Failed Fixes
1. **Named parameters on `TimeRangeFilter.between(startTime=, endTime=)`** — no effect; filter was never the issue
2. **Named parameters on `ReadRecordsRequest(recordType=, timeRangeFilter=)`** — no effect; request construction was not the issue
3. **Upgrading SDK from alpha12 to rc01** — did not fix deserialization of corrupt records; the `StepsRecord` constructor validation exists in both versions
4. **`require(startTime.isBefore(endTime))`** guard added before filter construction — confirmed filter was valid, did not fix the crash because the filter was never invalid

### Bypass Applied
Switched from `readRecords(StepsRecord)` to `client.aggregate(AggregateRequest(metrics = setOf(StepsRecord.COUNT_TOTAL), ...))`. The aggregate API computes step totals on the Health Connect service side without deserializing individual `StepsRecord` objects into the SDK's Kotlin types. The corrupt record is invisible to aggregate queries.

**No raw `StepsRecord` deserialization anywhere in the current codebase.**

### Cannot Fix At Source
The corrupt record lives in Health Connect's internal database. VigilBridge cannot delete it — HC does not expose a delete-by-ID API to apps. The user could manually delete it via:
Health Connect app → Data → Step count → Delete all / delete specific entries around 2026-05-29.

### Risk of Bypass
If the corrupt record's date falls within the aggregate time window, the aggregate service may or may not include it. From testing, the aggregate queries return sensible results despite the corrupt record existing. The HC service appears to handle corrupt records more gracefully at the aggregate layer than at the record-deserialization layer.

---

## BUG-003: UnavailableScreen Uses Magic Integer Literals

**Severity:** Low — not a runtime crash; wrong message displayed if constants change  
**Status:** Open  
**Introduced:** v0.2 refactor (moving composables to `ui` package)  

### Symptom
`UnavailableScreen` in `DashboardScreen.kt` checks:
```kotlin
val message = when (status) {
    1 -> "Health Connect not installed"
    3 -> "Health Connect needs updating"
    else -> "Health Connect unavailable (status=$status)"
}
```
`1` and `3` are hardcoded instead of using `HealthConnectClient.SDK_UNAVAILABLE` and `HealthConnectClient.SDK_UNAVAILABLE_PROVIDER_UPDATE_REQUIRED`.

### Root Cause
During the v0.2 refactor, `UnavailableScreen` was moved from `MainActivity.kt` (which imports `HealthConnectClient`) to `DashboardScreen.kt` (which was intentionally kept free of HC SDK imports at the composable level). The constants were replaced with literals as a quick fix to avoid adding the HC import to the UI file.

### Recommended Fix
Option A — Import the constants (simplest):
```kotlin
import androidx.health.connect.client.HealthConnectClient
when (status) {
    HealthConnectClient.SDK_UNAVAILABLE -> "Health Connect not installed"
    HealthConnectClient.SDK_UNAVAILABLE_PROVIDER_UPDATE_REQUIRED -> "Health Connect needs updating"
```

Option B — Pass resolved string from `MainActivity` (cleaner architecture):
```kotlin
// MainActivity computes the message, passes String to UnavailableScreen
// UnavailableScreen(message: String) — no HC dependency in UI layer
```

---

## BUG-004: No Error Surface When All Queries Fail

**Severity:** Medium — silent failure, user confusion  
**Status:** Open  

### Symptom
If Health Connect service is unavailable, all 5 queries in `HealthRepository.load()` fail silently. `DashboardUiState` shows `—` for every metric with no explanation. User cannot distinguish between "no data" and "query failed".

### Root Cause
Each query in `HealthRepository` catches `Exception` and returns `null`. `null` maps to `"—"` in `DashboardViewModel.toUiState()`. No aggregate error state is propagated. `DashboardUiState` has no `error` field.

### Recommended Fix
Add `val loadError: String?` to `DashboardUiState`. In `DashboardViewModel.refresh()`, catch top-level failure and set error. In `Dashboard` composable, show an error banner when `loadError != null`.

---

## BUG-005: collectAsState() Instead of collectAsStateWithLifecycle()

**Severity:** Low — minor resource inefficiency  
**Status:** Open (known trade-off, not worth fixing now)  

### Symptom
`DashboardScreen.kt` uses `vm.state.collectAsState()`. This continues collecting the StateFlow even when the app is in the background (screen off, app backgrounded).

### Root Cause
`collectAsStateWithLifecycle()` from `androidx.lifecycle:lifecycle-runtime-compose` was not added as a dependency to keep the dep tree minimal. `collectAsState()` was used as the available alternative.

### Impact
Minimal for this app. The StateFlow only emits when `refresh()` is called (not continuously). The collection overhead while backgrounded is negligible.

### Recommended Fix
Add `lifecycle-runtime-compose:2.10.0` to `build.gradle.kts`:
```kotlin
implementation("androidx.lifecycle:lifecycle-runtime-compose:2.10.0")
```
Replace in `DashboardScreen.kt`:
```kotlin
import androidx.lifecycle.compose.collectAsStateWithLifecycle
val state by vm.state.collectAsStateWithLifecycle()
```

---

## BUG-006: Resting Heart Rate Not Verified on Device

**Severity:** Medium — feature may silently return `—` always  
**Status:** Deferred to Phase 2  

### Symptom
`RestingHeartRateRecord.BPM_AVG` aggregate was implemented in `HealthRepository` but never confirmed to return a non-null value on the S24 Ultra.

### Root Cause
Samsung Health may not write `RestingHeartRateRecord` entries to Health Connect, even if it computes resting HR internally. Health Connect data sharing requires explicit configuration in Samsung Health.

### Evidence
None. Feature was implemented at end of session without device verification.

### Investigation Steps
1. Open Health Connect app on device
2. Check Data and access → All data → Resting heart rate
3. If empty: Samsung Health is not sharing this data type to Health Connect
4. If present: check that VigilBridge has `READ_RESTING_HEART_RATE` permission granted

### Fallback (Phase 2 implementation)
Compute approximate resting HR as minimum `HeartRateRecord.BPM` between 02:00–06:00 (deep sleep window, lowest HR). `HeartRateRecord` is shared by Samsung Health to Health Connect. Deferred from Phase 1: resting HR is a data quality issue, not a pipeline reliability issue. Phase 1 objective was proving end-to-end ingestion, not data completeness.

---

## INV-001: Samsung Health vs Health Connect Sleep Model Discrepancy

**Severity:** High — trend analysis of sleep duration meaningless until resolved  
**Status:** RESOLVED — 2026-06-06  
**Discovered:** 2026-06-06

### Symptom
Samsung Health and Vigil report different values for the same sleep session:

| Source | Start | End | Duration |
|---|---|---|---|
| Samsung Health (ground truth) | 1:48 AM | 8:07 AM | Time in bed: 6h 19m / Actual sleep: 5h 42m |
| Vigil (Health Connect) | 1:48 AM | 6:21 AM | 4h 33m |

Vigil is short by ~1h 9m (actual sleep) to 1h 46m (time in bed). Start time matches — discrepancy is entirely in the end time.

### Hypotheses

1. **HC `SleepSessionRecord` contains multiple sub-sessions or stages.** Samsung Health may write sleep as a series of `SleepSessionRecord.Stage` entries. Vigil's current `readLastSleep()` may be selecting a sub-session (e.g., the first continuous sleep block ending at 6:21) rather than the full session ending at 8:07.

2. **Session selection window cuts short.** Vigil uses `prev-18:00 → today-10:00` with minimum 180 min. If HC writes the session end as after 10:00 AM, it would be excluded.

3. **Samsung Health's "actual sleep" excludes awake periods.** The 8:07 end is "time in bed"; Samsung Health deducts awake-in-bed time to compute 5h 42m "actual sleep". HC may store the actual sleep end (6:21) without the awake-in-bed tail. In this case Vigil's 6:21 end time may be correct but is missing the awake segment.

4. **Multiple HC `SleepSessionRecord` objects for one night.** Samsung Health may write short-nap or awake-in-bed intervals as separate records. Vigil selects "most recent ≥180 min" and may miss a later record.

### Investigation Steps (next session)
1. In `VitalsSyncWorker.doWork()` or a test screen, read all `SleepSessionRecord` entries for the past 48h using `readRecords()` (not aggregate). Log each record's `startTime`, `endTime`, `stages` list.
2. Look for a record ending at ~8:07 AM IST. If not present, look at `stages` within the 1:48–8:07 window.
3. Compare `SleepSessionRecord.stages` breakdown to Samsung Health's stage graph.
4. Determine: does "actual sleep" = sum of non-AWAKE stage durations? Does HC expose this or must Vigil compute it from stages?

### Root Cause (Confirmed)
Samsung Health splits one night's sleep into two `SleepSessionRecord` objects:
- Session 1: `2026-06-05T20:18:00Z → 2026-06-06T00:51:00Z` (273 min, 54 stages)
- Session 2: `2026-06-06T01:01:00Z → 2026-06-06T02:37:00Z` (96 min, 38 stages)
- Gap: 10 min

Vigil's old 180-min minimum filter selected only session 1 (273 min) and discarded session 2 (96 min). Stage arithmetic: actual sleep = sum of non-AWAKE/non-OUT_OF_BED stage durations = 342 min = 5h42m across both sessions. Matches Samsung Health exactly.

### Fix Applied
- `SleepMerger.kt`: pure Kotlin merge algorithm. Groups sessions by ≤30-min gap tolerance, picks group with most actual sleep, rejects groups < 3h actual sleep.
- `HealthRepository.kt`: calls merger, logs merged summary.
- `DashboardViewModel.kt`: displays `actualSleepMinutes`, end time from merged block.
- `VigilApiClient.kt`: sends `actualSleepMinutes`, `timeInBedMinutes`, `sleepSessionsCount`.
- `extractor.py`: `sleep_duration_hours` from `actualSleepMinutes`; adds `time_in_bed_hours`, `sleep_sessions_count`; deprecates `sleep_midpoint_hour`.
- `SleepMergerTest.kt`: 11 unit tests covering INV-001 scenario, gap boundaries, edge cases.

### Verification Evidence (2026-06-06)
Android logcat: `Merged sleep: sessions=2 start=2026-06-05T20:18:00Z end=2026-06-06T02:37:00Z actual=342min timeInBed=379min`

Postgres (confirmed in DB):
| Metric | Value | Status |
|--------|-------|--------|
| `sleep_start_hour` | 1.8 (1:48 AM IST) | ✓ |
| `sleep_end_hour` | 8.1167 (8:07 AM IST) | ✓ matches Samsung Health |
| `time_in_bed_hours` | 6.3167 (6h19m) | ✓ NEW metric, matches Samsung Health |
| `sleep_sessions_count` | 2.0 | ✓ NEW metric |
| `sleep_duration_hours` | 4.55 | old row (boundary diff, stuck — will be 5.70 from next night) |

Note: `sleep_duration_hours` for June 5-6 night is stuck at 4.55 due to `ON CONFLICT DO NOTHING`. Correct 5.70 value will appear starting June 6-7 night.

### Code Location
`app/.../data/SleepMerger.kt`, `HealthRepository.kt`, `backend/app/services/extractor.py`

---

## BUG-007: versionName Mismatch

**Severity:** Cosmetic  
**Status:** Open  

### Symptom
`app/build.gradle.kts` has `versionName = "1.0"` and `versionCode = 1`. The app is architecturally at v0.2.

### Fix
```kotlin
versionCode = 2
versionName = "0.2"
```
