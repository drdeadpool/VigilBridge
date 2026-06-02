# VigilBridge — Next 10 Development Tasks
Last updated: 2026-06-02.

---

## Task 1 — Fix Permission Auto-Transition (BLOCKER)

**Priority:** P0 — must fix before any other work  
**Difficulty:** Easy  
**Estimated time:** 20 minutes  
**Depends on:** Nothing  

**Problem:** After granting permissions, app stays on `PermissionScreen`. User must tap "Re-check Permissions" manually.

**Fix:** Hoist `permissionsGranted` to Activity-level `MutableState` and re-check inside the launcher callback.

**Exact change required in `MainActivity.kt`:**
```kotlin
// 1. Move permissionsGranted OUT of setContent, into the Activity class:
private val permissionsGranted = mutableStateOf(false)

// 2. Update launcher to re-check after result:
private val requestPermissionsLauncher = registerForActivityResult(
    PermissionController.createRequestPermissionResultContract()
) { _ ->
    lifecycleScope.launch {
        try {
            val granted = healthConnectClient?.permissionController?.getGrantedPermissions()
            permissionsGranted.value = granted != null && PERMISSIONS.all { it in granted }
        } catch (e: Exception) {
            Log.e(TAG, "Post-grant permission check failed", e)
        }
    }
}

// 3. In setContent, read the Activity-level state:
val pg by permissionsGranted  // delegates to Activity MutableState

// 4. Remove the LaunchedEffect that initializes it inside setContent — 
//    move the initial check to onCreate() instead:
override fun onCreate(...) {
    ...
    lifecycleScope.launch {
        val granted = healthConnectClient?.permissionController?.getGrantedPermissions()
        permissionsGranted.value = granted != null && PERMISSIONS.all { it in granted }
    }
}
```

**Imports needed:** `androidx.lifecycle.lifecycleScope`, `kotlinx.coroutines.launch`

---

## Task 2 — Add onResume Permission Recheck

**Priority:** P1  
**Difficulty:** Easy  
**Estimated time:** 15 minutes  
**Depends on:** Task 1 (needs Activity-level permissionsGranted)  

**Problem:** If user grants permissions via Android Settings while app is backgrounded, `permissionsGranted` is stale on return.

**Fix:** Override `onResume()` in `MainActivity` to re-check permissions:
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

## Task 3 — Fix UnavailableScreen Integer Literals

**Priority:** P1  
**Difficulty:** Trivial  
**Estimated time:** 5 minutes  
**Depends on:** Nothing  

**Problem:** `UnavailableScreen` in `DashboardScreen.kt` uses `1` and `3` as magic numbers instead of `HealthConnectClient.SDK_UNAVAILABLE` and `HealthConnectClient.SDK_UNAVAILABLE_PROVIDER_UPDATE_REQUIRED`.

**Fix:** Either import `HealthConnectClient` in `DashboardScreen.kt`, or pass a resolved `String` from `MainActivity` instead of `Int`:

Option A — import constants:
```kotlin
import androidx.health.connect.client.HealthConnectClient
// replace 1 with HealthConnectClient.SDK_UNAVAILABLE
// replace 3 with HealthConnectClient.SDK_UNAVAILABLE_PROVIDER_UPDATE_REQUIRED
```

Option B — pass string from Activity (cleaner, decouples UI from HC):
```kotlin
// In MainActivity: compute message string and pass to UnavailableScreen
// Change UnavailableScreen signature to: fun UnavailableScreen(message: String)
```

---

## Task 4 — Update versionName to "0.2"

**Priority:** P2  
**Difficulty:** Trivial  
**Estimated time:** 2 minutes  
**Depends on:** Nothing  

**Fix:** In `app/build.gradle.kts`, change:
```kotlin
versionName = "1.0"
```
to:
```kotlin
versionName = "0.2"
```
And bump `versionCode = 2`.

---

## Task 5 — Verify Resting Heart Rate on Device

**Priority:** P1  
**Difficulty:** Testing only (no code)  
**Estimated time:** 10 minutes  
**Depends on:** Nothing  

**Action:** Run the app on the S24 Ultra. Check whether "RESTING HEART RATE" card shows a value or `—`.

If `—`:
- Open Health Connect app → Data & access → verify `RestingHeartRateRecord` permission granted to VigilBridge
- Check if Samsung Health is writing resting HR to Health Connect (Samsung Health → Settings → Connected services → Health Connect → data types)
- If Samsung Health does NOT share RestingHeartRateRecord, switch to `HeartRateRecord.BPM_MIN` as a proxy: minimum HR over last 7 nights (8 PM–8 AM windows)

---

## Task 6 — Add Error State to Dashboard

**Priority:** P2  
**Difficulty:** Easy  
**Estimated time:** 30 minutes  
**Depends on:** Nothing  

**Problem:** If all queries fail silently, the user sees a dashboard full of `—` with no explanation.

**Fix:** Add `val loadError: String?` to `DashboardUiState`. In `HealthRepository.load()`, if ALL metrics fail, surface a meaningful error. In `Dashboard` composable, show a banner when `loadError != null`.

```kotlin
data class DashboardUiState(
    ...
    val loadError: String? = null,
)
```

---

## Task 7 — Extract SleepSummary Domain Model

**Priority:** P3  
**Difficulty:** Easy  
**Estimated time:** 20 minutes  
**Depends on:** Nothing  

**Problem:** `DashboardViewModel` currently depends on `SleepSessionRecord` (a Health Connect SDK type). This couples the ViewModel to the HC SDK, making testing harder and future migration (e.g., to a different data source) more complex.

**Fix:** Create `data/models/SleepSummary.kt`:
```kotlin
data class SleepSummary(
    val startTime: java.time.Instant,
    val endTime: java.time.Instant,
    val durationMinutes: Long,
)
```
Convert in `HealthRepository.readLastSleep()` before returning. Update `RawDashboard` to use `SleepSummary?` instead of `SleepSessionRecord?`.

---

## Task 8 — Add SpO2 and Respiratory Rate Metrics

**Priority:** P2  
**Difficulty:** Easy (follows established pattern)  
**Estimated time:** 45 minutes  
**Depends on:** Tasks 5 (understand which HC records device actually writes)  

**New records to add:**
- `OxygenSaturationRecord` — `OxygenSaturationRecord.PERCENTAGE_AVG` (SpO2 %)
- `RespiratoryRateRecord` — `RespiratoryRateRecord.RATE_AVG` (breaths/min)

**Pattern:** Identical to resting HR. Add permission, add aggregate query in `HealthRepository`, add field to `RawDashboard`, format in `DashboardViewModel.toUiState()`, add `MetricCard` in dashboard.

**CAVEAT:** Same risk as resting HR — Samsung Health may not write these to Health Connect. Verify device support before adding.

---

## Task 9 — Add Navigation Between Screens

**Priority:** P3  
**Difficulty:** Medium  
**Estimated time:** 2 hours  
**Depends on:** Nothing  

**Context:** Currently the entire app is one screen. As more sections are added (historical data, trends, settings), navigation will be needed.

**Recommended approach:** Add `androidx.navigation:navigation-compose` and define:
- `Route.Dashboard` (current screen)
- `Route.Settings` (future: permissions management, data source selection)
- `Route.History` (future: 30-day trends)

Use `NavHost` in `MainActivity.setContent` with `BottomNavigationBar`.

---

## Task 10 — Write Unit Tests for ViewModel and Repository

**Priority:** P3  
**Difficulty:** Medium  
**Estimated time:** 2–3 hours  
**Depends on:** Task 7 (domain model extraction makes testing cleaner)  

**Test targets:**
1. `DashboardViewModel.toUiState()` — pure function, no HC dependency. Test formatting of steps, sleep duration, HR.
2. `HealthRepository.aggregateSteps()` — requires faking `HealthConnectClient`. Either use a hand-written fake or Mockito.

**Setup needed:**
```kotlin
testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test:1.10.2")
testImplementation("app.cash.turbine:turbine:1.x")  // for Flow testing
```

---

## Task Dependency Graph

```
T1 (permission fix)
  └─ T2 (onResume recheck)

T3 (integer literals)  — standalone
T4 (versionName)       — standalone
T5 (verify resting HR) — standalone, blocks T8

T6 (error state)       — standalone
T7 (domain model)      — standalone, prerequisite for T10

T8 (SpO2/respiratory)  — after T5
T9 (navigation)        — standalone
T10 (tests)            — after T7
```

## Recommended Execution Order

```
Week 1: T1 → T2 → T3 → T4 → T5
Week 2: T6 → T7 → T8
Week 3: T9 → T10
```
