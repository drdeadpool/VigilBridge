package com.batman.vigilbridge.data

import android.util.Log
import androidx.health.connect.client.HealthConnectClient
import androidx.health.connect.client.records.RestingHeartRateRecord
import androidx.health.connect.client.records.SleepSessionRecord
import androidx.health.connect.client.records.StepsRecord
import androidx.health.connect.client.request.AggregateRequest
import androidx.health.connect.client.request.ReadRecordsRequest
import androidx.health.connect.client.time.TimeRangeFilter
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId

private const val TAG = "HealthRepository"

data class RawDashboard(
    val stepsToday: Long?,
    val steps7d: Long?,
    val steps30d: Long?,
    val lastSleep: SleepSummary?,
    val restingHeartRateBpm: Long?,
)

class HealthRepository(
    private val client: HealthConnectClient,
    private val dao: VitalsDao,
) {

    suspend fun load(): RawDashboard {
        val now = Instant.now()
        val zone = ZoneId.systemDefault()
        val todayStart = LocalDate.now(zone).atStartOfDay(zone).toInstant()

        val raw = RawDashboard(
            stepsToday = aggregateSteps(
                TimeRangeFilter.between(startTime = todayStart, endTime = now)
            ),
            steps7d = aggregateSteps(
                TimeRangeFilter.between(startTime = now.minusSeconds(7L * 86_400), endTime = now)
            ),
            steps30d = aggregateSteps(
                TimeRangeFilter.between(startTime = now.minusSeconds(30L * 86_400), endTime = now)
            ),
            lastSleep = readLastSleep(now),
            restingHeartRateBpm = readRestingHR(now),
        )

        try {
            dao.insert(raw.toSnapshot(now))
        } catch (e: Exception) {
            Log.e(TAG, "Snapshot write failed: ${e.message}")
        }

        return raw
    }

    private fun RawDashboard.toSnapshot(now: Instant) = VitalsSnapshot(
        timestampMs = now.toEpochMilli(),
        stepsToday = stepsToday,
        steps7d = steps7d,
        steps30d = steps30d,
        sleepDurationMinutes = lastSleep?.actualSleepMinutes,
        sleepStartMs = lastSleep?.startTime?.toEpochMilli(),
        sleepEndMs = lastSleep?.endTime?.toEpochMilli(),
        restingHrBpm = restingHeartRateBpm,
    )

    private suspend fun aggregateSteps(filter: TimeRangeFilter): Long? = try {
        client.aggregate(
            AggregateRequest(
                metrics = setOf(StepsRecord.COUNT_TOTAL),
                timeRangeFilter = filter,
            )
        )[StepsRecord.COUNT_TOTAL] ?: 0L
    } catch (e: Exception) {
        Log.e(TAG, "Steps aggregate failed: ${e.message}")
        null
    }

    private suspend fun readLastSleep(now: Instant): SleepSummary? = try {
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

        summary
    } catch (e: Exception) {
        Log.e(TAG, "Sleep read failed: ${e.message}")
        null
    }

    private suspend fun readRestingHR(now: Instant): Long? = try {
        client.aggregate(
            AggregateRequest(
                metrics = setOf(RestingHeartRateRecord.BPM_AVG),
                timeRangeFilter = TimeRangeFilter.between(
                    startTime = now.minusSeconds(7L * 86_400),
                    endTime = now,
                ),
            )
        )[RestingHeartRateRecord.BPM_AVG]
    } catch (e: Exception) {
        Log.e(TAG, "Resting HR failed: ${e.message}")
        null
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
