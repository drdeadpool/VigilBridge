package com.batman.vigilbridge.data

import android.os.RemoteException
import android.util.Log
import androidx.health.connect.client.HealthConnectClient
import androidx.health.connect.client.records.ActiveCaloriesBurnedRecord
import androidx.health.connect.client.records.HeartRateRecord
import androidx.health.connect.client.records.RestingHeartRateRecord
import androidx.health.connect.client.records.SleepSessionRecord
import androidx.health.connect.client.records.StepsRecord
import androidx.health.connect.client.request.AggregateRequest
import androidx.health.connect.client.request.ReadRecordsRequest
import androidx.health.connect.client.time.TimeRangeFilter
import kotlinx.coroutines.CancellationException
import java.io.IOException
import java.time.Instant
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.ZoneId

private const val TAG = "HealthRepository"

data class RawDashboard(
    val stepsToday: Long?,
    val steps7d: Long?,
    val steps30d: Long?,
    val lastSleep: SleepSummary?,
    val restingHeartRateBpm: Long?,
    val activeEnergyKcal: Double?,
)

class HealthRepository(
    private val client: HealthConnectClient,
) {

    suspend fun load(): HealthLoadResult {
        val now = Instant.now()
        val zone = ZoneId.systemDefault()
        val todayStart = LocalDate.now(zone).atStartOfDay(zone).toInstant()

        return HealthLoadResult(
            stepsToday = aggregateSteps(
                metric = "steps_today",
                TimeRangeFilter.between(startTime = todayStart, endTime = now)
            ),
            steps7d = aggregateSteps(
                metric = "steps_7d",
                TimeRangeFilter.between(startTime = now.minusSeconds(7L * 86_400), endTime = now)
            ),
            steps30d = aggregateSteps(
                metric = "steps_30d",
                TimeRangeFilter.between(startTime = now.minusSeconds(30L * 86_400), endTime = now)
            ),
            lastSleep = readLastSleep(now),
            restingHeartRate = readRestingHR(now),
            activeEnergy = aggregateActiveEnergy(
                TimeRangeFilter.between(startTime = todayStart, endTime = now)
            ),
        )
    }

    private suspend fun aggregateActiveEnergy(
        filter: TimeRangeFilter,
    ): MetricRead<Double> = readMetric("active_energy") {
        val total = client.aggregate(
            AggregateRequest(
                metrics = setOf(ActiveCaloriesBurnedRecord.ACTIVE_CALORIES_TOTAL),
                timeRangeFilter = filter,
            )
        )[ActiveCaloriesBurnedRecord.ACTIVE_CALORIES_TOTAL]
        total?.let { MetricRead.Value(it.inKilocalories) } ?: MetricRead.NoData
    }

    private suspend fun aggregateSteps(
        metric: String,
        filter: TimeRangeFilter,
    ): MetricRead<Long> = readMetric(metric) {
        MetricRead.Value(
            client.aggregate(
                AggregateRequest(
                    metrics = setOf(StepsRecord.COUNT_TOTAL),
                    timeRangeFilter = filter,
                )
            )[StepsRecord.COUNT_TOTAL] ?: 0L
        )
    }

    private suspend fun readLastSleep(now: Instant): MetricRead<SleepSummary> =
        readMetric("sleep") {
        val zone = ZoneId.systemDefault()
        val today = LocalDate.now(zone)
        val windowStart = today.minusDays(1).atTime(18, 0).atZone(zone).toInstant()
        val windowEnd   = today.atTime(10, 0).atZone(zone).toInstant()

        val sessions = client.readRecords(
            ReadRecordsRequest(
                recordType = SleepSessionRecord::class,
                timeRangeFilter = TimeRangeFilter.between(
                    startTime = windowStart,
                    endTime   = windowEnd,
                ),
                ascendingOrder = true,
                pageSize = 20,
            )
        ).records

        Log.d(TAG, "Sleep sessions in window [${windowStart}→${windowEnd}]: ${sessions.size}")
        sessions.forEach { s ->
            val mins = (s.endTime.epochSecond - s.startTime.epochSecond) / 60
            Log.d(TAG, "  session: start=${s.startTime} end=${s.endTime} total=${mins}min stages=${s.stages.size}")
        }

        val summary = mergeSleepSessions(sessions.map { it.toRaw() })

        if (summary != null) {
            Log.d(TAG, "Merged sleep: sessions=${summary.sessionCount} start=${summary.startTime} end=${summary.endTime} actual=${summary.actualSleepMinutes}min timeInBed=${summary.timeInBedMinutes}min")
        } else {
            Log.d(TAG, "No qualifying sleep in window")
        }

        summary?.let { MetricRead.Value(it) } ?: MetricRead.NoData
    }

    private suspend fun readRestingHR(now: Instant): MetricRead<Long> =
        readMetric("resting_hr") {
        // Stage 1: RestingHeartRateRecord — Samsung Health does not write this to Health Connect
        // on S24 Ultra. Check kept for forward compatibility.
        val restingValue = client.aggregate(
            AggregateRequest(
                metrics = setOf(RestingHeartRateRecord.BPM_AVG),
                timeRangeFilter = TimeRangeFilter.between(
                    startTime = now.minusSeconds(24L * 3600),
                    endTime = now,
                ),
            )
        )[RestingHeartRateRecord.BPM_AVG]
        if (restingValue != null) return@readMetric MetricRead.Value(restingValue)

        // Stage 2: Fallback — minimum HeartRateRecord BPM during 02:00–06:00 device-local time.
        // Samsung Health writes HeartRateRecord during sleep. BPM_MIN in this deep-sleep window
        // approximates resting HR. (BUG-006)
        val zone = ZoneId.systemDefault()
        val localNow = LocalDateTime.ofInstant(now, zone)
        val windowDate = if (localNow.hour >= 6) localNow.toLocalDate() else localNow.toLocalDate().minusDays(1)
        val windowStart = windowDate.atTime(2, 0).atZone(zone).toInstant()
        val windowEnd   = windowDate.atTime(6, 0).atZone(zone).toInstant()

        val fallbackValue = client.aggregate(
            AggregateRequest(
                metrics = setOf(HeartRateRecord.BPM_MIN),
                timeRangeFilter = TimeRangeFilter.between(windowStart, windowEnd),
            )
        )[HeartRateRecord.BPM_MIN]
        fallbackValue?.let { MetricRead.Value(it) } ?: MetricRead.NoData
    }

    private suspend fun <T> readMetric(
        metric: String,
        block: suspend () -> MetricRead<T>,
    ): MetricRead<T> = try {
        block()
    } catch (e: CancellationException) {
        throw e
    } catch (e: SecurityException) {
        failure(metric, HealthReadFailureKind.PERMISSION, e)
    } catch (e: IOException) {
        failure(metric, HealthReadFailureKind.IO, e)
    } catch (e: RemoteException) {
        failure(metric, HealthReadFailureKind.REMOTE, e)
    } catch (e: IllegalStateException) {
        failure(metric, HealthReadFailureKind.SERVICE_UNAVAILABLE, e)
    } catch (e: Exception) {
        failure(metric, HealthReadFailureKind.UNKNOWN, e)
    }

    private fun <T> failure(
        metric: String,
        kind: HealthReadFailureKind,
        error: Exception,
    ): MetricRead<T> {
        Log.e(TAG, "$metric read failed (${kind.name})", error)
        return MetricRead.Failure(
            HealthReadFailure(
                metric = metric,
                kind = kind,
                message = error.message,
            )
        )
    }
}

private fun SleepSessionRecord.toRaw() = RawSleepSession(
    startSeconds = startTime.epochSecond,
    endSeconds   = endTime.epochSecond,
    stages = stages.map { stage ->
        RawSleepStage(
            startSeconds = stage.startTime.epochSecond,
            endSeconds   = stage.endTime.epochSecond,
            stageType    = stage.stage,
        )
    },
)
