# VigilBridge — Next 10 Development Tasks
Last updated: 2026-06-03.

---

## Completed (do not re-do)

| Task | Status |
|---|---|
| Fix permission auto-transition | ✅ Done — `rememberLauncherForActivityResult` |
| Room database | ✅ Done — `VitalsSnapshot`, `VitalsDao`, `VigilDatabase` |
| WorkManager background sync | ✅ Done — `VitalsSyncWorker`, 15-min periodic |
| KSP + AGP 9.x compatibility | ✅ Done — KSP `2.2.10-2.0.2`, `disallowKotlinSourceSets=false` |

---

## Task 1 — Verify Resting HR Data on Device (BLOCKER FOR HEART SECTION)

**Priority:** P0 — required before expanding heart metrics  
**Difficulty:** Testing only, no code  
**Depends on:** Nothing

**Action:** Run app on S24 Ultra. Check if "RESTING HEART RATE" card shows a value or `—`.

If `—`:
1. Open Health Connect → Data and access → All data → Resting heart rate. If empty, Samsung Health isn't sharing.
2. In Samsung Health: Settings → Connected services → Health Connect → verify resting HR is included.
3. If still empty, use fallback: query `HeartRateRecord` with `HeartRateRecord.BPM_MIN` over 2am–6am window as a proxy for resting HR.

**Gate:** Heart section shows real data before adding SpO2/respiratory.

---

## Task 2 — Add onResume Permission Recheck

**Priority:** P1 — edge case but users hit it  
**Difficulty:** Easy — 15 minutes  
**Depends on:** Nothing

**Problem:** User grants via Settings while app backgrounded → returns to app → `permissionsGranted` stale.

**Fix:** Override `onResume()` in `MainActivity`:
```kotlin
override fun onResume() {
    super.onResume()
    lifecycleScope.launch {
        try {
            val granted = healthConnectClient?.permissionController?.getGrantedPermissions()
            permissionsGranted = granted != null && PERMISSIONS.all { it in granted }
        } catch (e: Exception) {
            Log.e(TAG, "onResume permission check failed", e)
        }
    }
}
```
**Note:** `permissionsGranted` must first be hoisted from `setContent` Compose scope to Activity field for this to work. Currently it's still Compose-local — the launcher callback works because it uses `rememberLauncherForActivityResult` inside the Compose scope, but `onResume` is Activity-level and can't access Compose state.

**Correct approach:** Hoist `permissionsGranted` to `private val permissionsGranted = mutableStateOf(false)` at Activity level, then read via `val pg by permissionsGranted` inside `setContent`.

---

## Task 3 — Fix UnavailableScreen Magic Literals

**Priority:** P2 — fragile, not runtime-breaking  
**Difficulty:** Trivial — 5 minutes  
**Depends on:** Nothing

**Fix in `DashboardScreen.kt`:**
```kotlin
import androidx.health.connect.client.HealthConnectClient
val message = when (status) {
    HealthConnectClient.SDK_UNAVAILABLE -> "Health Connect not installed"
    HealthConnectClient.SDK_UNAVAILABLE_PROVIDER_UPDATE_REQUIRED -> "Health Connect needs updating"
    else -> "Health Connect unavailable (status=$status)"
}
```

---

## Task 4 — Update versionName and versionCode

**Priority:** P2 — cosmetic  
**Difficulty:** Trivial  
**Depends on:** Nothing

In `app/build.gradle.kts`:
```kotlin
versionCode = 3
versionName = "0.3"
```

---

## Task 5 — Add Error State to DashboardUiState

**Priority:** P2  
**Difficulty:** Easy — 30 minutes  
**Depends on:** Nothing

**Problem:** If all HC queries fail, dashboard shows all `—` with no explanation.

**Fix:**
```kotlin
data class DashboardUiState(
    ...
    val loadError: String? = null,
)
```
In `DashboardViewModel.refresh()`, catch top-level failure and set `loadError`. In `Dashboard` composable, show error banner when `loadError != null`.

---

## Task 6 — Verify WorkManager Background Execution

**Priority:** P1 — needed to confirm background sync actually runs  
**Difficulty:** Testing only  
**Depends on:** Nothing

**Action:**
1. Install app on S24 Ultra.
2. Open app, grant permissions, wait for dashboard to load.
3. Background the app for 15+ minutes.
4. Use Android Studio → App Inspection → WorkManager to verify `vigil_vitals_sync` job ran.
5. Or: `adb shell dumpsys jobscheduler | grep vigil` to see job state.
6. Check Room DB via App Inspection → Database Inspector → `vitals_snapshots` table for new rows.

---

## Task 7 — Add SpO2 and Respiratory Rate Metrics

**Priority:** P2 — after Task 1 and Task 6 confirmed  
**Difficulty:** Easy — follows existing pattern  
**Depends on:** Task 1 (know which HC record types device actually provides)

**New records:**
- `OxygenSaturationRecord` — `OxygenSaturationRecord.PERCENTAGE_AVG`
- `RespiratoryRateRecord` — `RespiratoryRateRecord.RATE_AVG`

**Pattern per metric:**
1. Add permission to manifest
2. Add to `PERMISSIONS` set in `MainActivity` and `VitalsSyncWorker`
3. Add aggregate query in `HealthRepository`
4. Add field to `RawDashboard`
5. Add nullable column to `VitalsSnapshot` (nullable Long → no migration)
6. Format in `DashboardViewModel.toUiState()`
7. Add `MetricCard` in `Dashboard`

---

## Task 8 — Extract SleepSummary Domain Model

**Priority:** P3  
**Difficulty:** Easy — 20 minutes  
**Depends on:** Nothing

`RawDashboard.lastSleep: SleepSessionRecord?` couples ViewModel to HC SDK. Create `data/SleepSummary.kt`:
```kotlin
data class SleepSummary(val startTime: Instant, val endTime: Instant, val durationMinutes: Long)
```
Convert in `HealthRepository.readLastSleep()`. Update `RawDashboard` and `VitalsSnapshot.toSnapshot()`.

---

## Task 9 — Dashboard Shows Last Known Values on Startup

**Priority:** P3 — UX improvement  
**Difficulty:** Medium — 45 minutes  
**Depends on:** Room (done)

**Problem:** Dashboard shows `—` on first load until HC query completes (typically 1–2s).

**Fix:** In `DashboardViewModel.init`, first load from Room (`dao.getLatest()`), map to UiState, show immediately. Then trigger HC refresh which replaces with fresh data.

Add `VitalsSnapshot.toUiState()` extension or a mapper function. ViewModel init becomes:
```kotlin
init {
    viewModelScope.launch {
        val cached = dao.getLatest()
        if (cached != null) _state.value = cached.toUiState()
        refresh()
    }
}
```
Requires passing `dao` into ViewModel (update factory).

---

## Task 10 — Write Unit Tests for ViewModel

**Priority:** P3  
**Difficulty:** Medium — 1–2 hours  
**Depends on:** Task 8 (cleaner model makes testing easier)

Target: `DashboardViewModel.toUiState()` is a pure function. Test formatting of steps, sleep duration, HR.

Setup needed:
```kotlin
testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test:1.10.2")
testImplementation("app.cash.turbine:turbine:1.2.0")
```

---

## Dependency Graph

```
T1 (verify resting HR) — standalone, blocks T7
T2 (onResume recheck) — standalone
T3 (magic literals)   — standalone
T4 (versionName)      — standalone
T5 (error state)      — standalone
T6 (verify WorkManager) — standalone, confirms background sync
T7 (SpO2/respiratory) — after T1
T8 (SleepSummary)     — standalone, prerequisite for T10
T9 (cached startup)   — after Room (done)
T10 (tests)           — after T8
```

## Recommended Execution Order

```
Week 1: T6 → T1 → T2 → T3 → T4
Week 2: T5 → T9 → T7
Week 3: T8 → T10
```
