package com.batman.vigilbridge.sync

import android.content.Context
import androidx.room.withTransaction
import com.batman.vigilbridge.data.RawDashboard
import com.batman.vigilbridge.data.SyncOutboxItem
import com.batman.vigilbridge.data.VigilDatabase
import com.batman.vigilbridge.data.VitalsSnapshot
import com.batman.vigilbridge.network.VigilApiClient
import com.batman.vigilbridge.work.OutboxUploadWorker
import java.time.Instant
import java.util.UUID

class SnapshotCaptureStore(
    context: Context,
    private val database: VigilDatabase,
) {
    private val appContext = context.applicationContext

    suspend fun persistAndEnqueue(
        dashboard: RawDashboard,
        capturedAt: Instant,
    ) {
        val eventId = UUID.randomUUID().toString()
        val payload = VigilApiClient.buildSnapshotPayload(
            context = appContext,
            raw = dashboard,
            timestamp = capturedAt,
            eventId = eventId,
        )
        val outboxItem = SyncOutboxItem(
            eventId = eventId,
            payloadJson = payload,
            createdAtMs = capturedAt.toEpochMilli(),
        )

        database.withTransaction {
            database.vitalsDao().insert(dashboard.toSnapshot(capturedAt))
            database.syncOutboxDao().insert(outboxItem)
        }
        OutboxUploadWorker.enqueue(appContext)
    }
}

private fun RawDashboard.toSnapshot(capturedAt: Instant) = VitalsSnapshot(
    timestampMs = capturedAt.toEpochMilli(),
    stepsToday = stepsToday,
    steps7d = steps7d,
    steps30d = steps30d,
    sleepDurationMinutes = lastSleep?.actualSleepMinutes,
    sleepStartMs = lastSleep?.startTime?.toEpochMilli(),
    sleepEndMs = lastSleep?.endTime?.toEpochMilli(),
    restingHrBpm = restingHeartRateBpm,
    activeEnergyKcal = activeEnergyKcal,
)
