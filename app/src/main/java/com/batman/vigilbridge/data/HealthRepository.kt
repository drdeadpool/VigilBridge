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
    val lastSleep: SleepSessionRecord?,
    val restingHeartRateBpm: Long?,
)

class HealthRepository(private val client: HealthConnectClient) {

    suspend fun load(): RawDashboard {
        val now = Instant.now()
        val zone = ZoneId.systemDefault()
        val todayStart = LocalDate.now(zone).atStartOfDay(zone).toInstant()

        return RawDashboard(
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
    }

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

    private suspend fun readLastSleep(now: Instant): SleepSessionRecord? = try {
        client.readRecords(
            ReadRecordsRequest(
                recordType = SleepSessionRecord::class,
                timeRangeFilter = TimeRangeFilter.between(
                    startTime = now.minusSeconds(48L * 3_600),
                    endTime = now,
                ),
                ascendingOrder = false,
                pageSize = 1,
            )
        ).records.firstOrNull()
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
