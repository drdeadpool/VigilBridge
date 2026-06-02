# VigilBridge — Lessons Learned
Session: 2026-06-02. VigilBridge v0.1 and v0.2 development.

---

## What Worked

### 1. Evidence-First Debugging
The entire corrupt StepsRecord investigation succeeded because every hypothesis was tested with evidence before applying a fix. Adding targeted `Log.d` statements at each step (STEP1 through STEP5) before attempting any code change produced the exact stacktrace, field values, and execution path needed to identify the root cause. This is the correct approach for Health Connect bugs where the SDK error messages are misleading.

### 2. Cross-Record Control Test
Proving that `SleepSessionRecord` succeeded with the exact same `TimeRangeFilter` was the pivotal insight. Without this control, investigation would have continued on `TimeRangeFilter` construction for much longer. Whenever a Health Connect query fails, immediately run the same query with a different record type. If it passes, the filter is valid and the problem is record-type-specific.

### 3. Binary Search Window Isolation
Systematically testing 1h → 24h → 3d → 4d → 4.25d → 4.50d windows to isolate the corrupt record was effective and methodical. The approach of testing progressively larger windows (not smaller) was correct because it established a safe baseline first, then expanded until failure.

### 4. javap for API Discovery
When the build failed with `Unresolved reference: nextPageToken`, the correct fix was to inspect the actual SDK bytecode rather than trust documentation or prior knowledge. Running `javap -p` on the classes.jar confirmed:
- `ReadRecordsResponse` has `getPageToken()` (not `getNextPageToken()`)
- `ReadRecordsRequest` accepts `pageToken: String?` as constructor parameter
- `RestingHeartRateRecord` has `BPM_AVG`, `BPM_MIN`, `BPM_MAX` aggregate metrics

**The `javap` command is the ground truth for Health Connect API in alpha/RC releases where documentation is incomplete.**

### 5. Aggregate API as Corruption Bypass
Switching from `readRecords(StepsRecord)` to `client.aggregate(AggregateRequest)` was the right pragmatic decision. The aggregate API bypasses per-record deserialization entirely. This solved the immediate crash and delivered working step counts without needing to clean the device's Health Connect database.

### 6. Page-by-Page Pagination Scan
Using `pageSize=1, ascendingOrder=true` with pagination to scan individual records was the correct approach to isolating the specific corrupt entry. This technique is reusable for any future Health Connect deserialization bug investigation.

### 7. Incremental Diagnostic UI
Building diagnostic tools directly into the app UI (test buttons, result cards) was far more effective than relying on Logcat alone. On a physical device, having the results displayed on screen eliminated the need to keep ADB connected and allowed faster iteration. The buttons stayed in the UI until investigation was complete, then were cleanly removed.

### 8. ViewModel with StateFlow
The `DashboardViewModel + StateFlow<DashboardUiState>` pattern worked cleanly. `init { refresh() }` triggers data load automatically on first composition. `viewModelScope` cancels cleanly on ViewModel destruction. All formatting logic in `toUiState()` keeps the composables pure display components.

---

## What Failed and Wasted the Most Time

### 1. Assuming TimeRangeFilter Was the Bug (Largest Time Sink)
The error message `"startTime must be before endTime"` directly caused investigation of `TimeRangeFilter` construction even though the filter was always valid. Applied multiple unnecessary fixes:
- Added named parameters to `TimeRangeFilter.between(startTime=, endTime=)`
- Added named parameters to `ReadRecordsRequest(recordType=, timeRangeFilter=)`
- Added `require(startTime.isBefore(endTime))` guard
- Added epoch millisecond logging

None of these were the problem. The error message described the corrupt record's own fields, not the query filter. **Health Connect SDK error messages from deserialization can appear to describe the query rather than the data.**

**Lesson:** When a Health Connect exception says "startTime must be before endTime," immediately check the stacktrace. If `StepsRecord.<init>()` or `RecordConvertersKt.toSdkStepsRecord()` is in the stack, the problem is a corrupt stored record, not your query.

### 2. Attempting to Inspect SDK JARs Before Building With Correct Version
Early attempts to inspect the SDK JAR using Bash tools (to understand `ReadRecordsResponse` field names) used paths that didn't exist or required `jar.exe` not on the standard PATH. Time was wasted before discovering that `jar.exe` and `javap.exe` live at `"C:\Program Files\Android\Android Studio\jbr\bin\"`.

**Lesson:** On Windows, Android Studio ships its own JDK. Always use:
```
/c/Program Files/Android/Android Studio/jbr/bin/javap.exe
/c/Program Files/Android/Android Studio/jbr/bin/jar.exe
```
Set `JAVA_HOME` for Gradle: `export JAVA_HOME="/c/Program Files/Android/Android Studio/jbr"`

### 3. Over-Engineering the TimeRangeFilter Fix
Named parameters (`startTime=`, `endTime=`) were applied to `TimeRangeFilter.between()` on the theory that alpha-12 had argument-order bugs. This was speculative. The actual SDK bytecode (confirmed via `javap`) shows `TimeRangeFilter.between(Instant startTime, Instant endTime)` with correct parameter order in all versions. Named parameters have no effect on method dispatch for `@JvmStatic` methods — they're a Kotlin compiler feature that maps to positional args in bytecode.

### 4. Proposing SDK Version Fixes Before Confirming Root Cause
Recommending the alpha-12 → rc01 upgrade as a potential fix for the crash was premature. The upgrade did not fix the crash because the bug was in the stored data, not the SDK version. The upgrade was still worth doing (RC01 is more stable than alpha-12), but attributing the crash to alpha-12 without evidence wasted one investigation cycle.

---

## SDK Pitfalls

### Health Connect Alpha/RC SDK Error Messages Are Misleading
`IllegalArgumentException: startTime must be before endTime` can originate from:
1. `TimeRangeFilter` validation (during filter construction)
2. `StepsRecord.<init>()` validation (during record deserialization)

Case 1 fires at `TimeRangeFilter.between()` call site (STEP2).
Case 2 fires at `readRecords()` (STEP3), well after the filter was successfully created.

The same error message for two completely different causes is the SDK's biggest documentation gap.

### API Field Names Differ From Documentation
`ReadRecordsResponse` exposes `pageToken` (not `nextPageToken`, not `continuationToken`). Always verify with `javap` before assuming field names in alpha/RC SDK releases. Documentation lags the bytecode.

### `TimeRangeFilter.between()` Does Not Validate On Construction in alpha-12
In alpha-12, `TimeRangeFilter.between(start, end)` could be constructed without throwing even when `start >= end`. Validation only fired when the request was serialized inside `readRecords()`. This made STEP2 pass and STEP3 throw, misleadingly suggesting the problem was in `readRecords()` construction rather than the filter. In rc01 this may have changed, but should not be assumed.

### pageSize=1 Pagination Works But Is Fragile for Error Recovery
When paginating with `pageSize=1` and the current page's record is corrupt, the SDK throws during deserialization before returning anything — including the page token. There is no way to skip a corrupt record and continue pagination. The only options are:
1. Narrow the time window to exclude the corrupt record
2. Use aggregate APIs that don't deserialize individual records

### Health Connect Requires Real Device Testing
The emulator does not have Health Connect installed by default. The corrupt data scenario cannot be reproduced on an emulator. All meaningful testing for this project requires a physical device with Samsung Health (or another HC-compatible app) that has been actively recording data.

### RestingHeartRateRecord Availability Is Not Guaranteed
`RestingHeartRateRecord` is a Health Connect record type, but whether it contains data depends on whether the user's fitness app (Samsung Health, Fitbit, Garmin Connect, etc.) is configured to sync this specific record type to Health Connect. Many apps sync `HeartRateRecord` but not `RestingHeartRateRecord`. Verify before building features that depend on it.

### Health Connect Permission Grant Does Not Update Compose State Automatically
The `PermissionController.createRequestPermissionResultContract()` result contract fires a callback at the Activity level. Compose state inside `setContent {}` is not accessible from this callback without explicit bridging. This is an architectural constraint, not a bug in Health Connect. Any app that checks permissions inside Compose and grants them via a system dialog will face this problem.

---

## Health Connect Gotchas

### 1. Data Corruption Happens
Health Connect stores records written by multiple apps. Any app with write permission can insert a `StepsRecord` with `startTime >= endTime`. This is valid from the app's perspective (HC does not validate on write in all SDK versions) but corrupt from the reader's perspective. Do not assume all stored records are valid.

### 2. Aggregate and readRecords Have Different Failure Modes
`client.aggregate()` does not iterate individual records on the client side — it delegates computation to the Health Connect service. Corrupt individual records may not affect aggregate results. `client.readRecords()` deserializes every record in the range on the client side — one corrupt record aborts the entire batch.

**Design principle:** Prefer aggregate APIs when only aggregate values are needed. Only use `readRecords()` when individual record fields are required.

### 3. Permission Scope Is Per Record Type
Adding a new record type (e.g., `RestingHeartRateRecord`) to `PERMISSIONS` creates a new permission that existing users have not granted. On next launch, the permission screen re-appears even if the user previously granted all other permissions. Plan permission sets carefully — adding new types after initial release requires user re-engagement with the permission dialog.

### 4. HC SDK Version in Gradle Cache After Upgrade
When upgrading from alpha-12 to rc01, the old JAR remains in `~/.gradle/caches`. `javap` inspection of the wrong JAR can produce incorrect API surface information. Always confirm which JAR is being inspected when debugging API discrepancies.

### 5. Health Connect Data Is Device-Local
Health Connect is not a cloud service. Data lives on the device. If the user factory resets, all Health Connect data is gone. The corrupt StepsRecord found in this session will be gone after a factory reset. This also means there is no way to pre-populate test data without a real fitness app installed and actively recording.

---

## Architecture Decisions That Should Not Be Repeated

### 1. Starting With Everything in MainActivity.kt
The initial prototype put all composables, all Health Connect queries, all state management, and all diagnostic tools in a single 600+ line `MainActivity.kt`. This was acceptable for v0.1 but created significant friction when:
- Diagnostic code needed to be removed without breaking production code
- v0.2 refactor required understanding what was production vs. temporary
- Debugging required understanding the entire file to find the relevant section

**Better approach:** Even for prototypes, create `data/` and `ui/` packages from the start. The initial overhead is 10 minutes; the payoff is every subsequent change.

### 2. Accumulating Diagnostic State Variables
By the peak of the debugging session, `VigilScreen` had 8 state variables:
`statusText, stepsText, sleepText, diagText, isolationText, isolation2Text, isolation3Text, scanText`

Each diagnostic phase added a new `var xText` and a new card. This created visual noise, difficult-to-follow state logic, and a large cleanup task at the end.

**Better approach:** Use a single `debugLog: List<String>` state that all diagnostic output appends to. One card shows the full log. One clear button resets it. No proliferation of named variables.

### 3. Blocking on False Leads Before Checking the Stacktrace
The investigation spent multiple turns fixing `TimeRangeFilter` construction before reading the stacktrace carefully. The stacktrace clearly showed `StepsRecord.<init>()` — which is inside the record constructor, not inside filter construction — but this was not checked until after several unnecessary fixes.

**Better approach:** For any SDK exception, the first action is to read the full stacktrace and identify the exact throwing class and method. Do not apply any fix until the throwing location is confirmed.

### 4. Not Verifying API Names Before Using Them
`nextPageToken` was used based on intuition/prior knowledge without verifying against the actual SDK. The build failure at line 571 was entirely avoidable. Verifying with `javap` before writing the pagination code would have prevented this.

**Better approach:** For any Health Connect alpha/RC field or method name, run `javap -p <ClassName>` on the local JAR before writing the code. Takes 30 seconds; saves a build cycle.

---

## Debugging Methodology That Succeeded

### The Step-By-Step Logging Technique
Adding numbered logging gates (STEP1, STEP2, STEP3...) with explicit values at each step, and using distinct error messages per step, was the most effective debugging technique in this session:
```kotlin
Log.d(TAG, "STEP1 startTime=$startTime endTime=$endTime isBefore=${startTime.isBefore(endTime)}")
// STEP2 try/catch with its own error message
// STEP3 try/catch with its own error message
```
This immediately showed which step failed, with the exact values at that point. Every Android Health Connect bug should be debugged this way first.

### Escalating Isolation Windows
1h → 24h → 3d → 4d → 4.25d → 4.50d → 4.25d-4.50d quartiles → page-by-page scan

Escalating from coarse to fine, confirming a safe baseline before each step, is efficient because:
- Failure at the first coarse window → problem is recent (narrow window needed)
- Failure only at large windows → problem is historical (large binary search space)
- This session: worked inward from 7d, found the corrupt record in ~6 window tests

### Using the App's Own UI as the Debug Harness
Building diagnostic buttons directly into the running app on the physical device was faster than ADB Logcat for this class of bug. The on-screen result cards showed pass/fail instantly without needing to tail logs. This is especially effective for Health Connect debugging where:
- The exact runtime values depend on device state
- Logcat requires keeping USB connected
- Multiple iterations are needed

### Inspecting SDK Bytecode Directly
When documentation is insufficient (common for alpha SDKs), `javap -p <ClassName>` on the local JAR is the definitive source of truth. Used to confirm:
- `ReadRecordsResponse.pageToken` (not `nextPageToken`)
- `ReadRecordsRequest` constructor parameter order
- `RestingHeartRateRecord.BPM_AVG` aggregate metric existence
- `AggregateRequest` constructor signature and defaults

This technique is broadly applicable: whenever an import resolves but a field/method reference doesn't compile, `javap` the class before guessing.
