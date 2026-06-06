package com.batman.vigilbridge.work

import android.content.Context
import android.util.Log
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import com.batman.vigilbridge.data.SyncOutboxStatus
import com.batman.vigilbridge.data.VigilDatabase
import com.batman.vigilbridge.network.UploadResult
import com.batman.vigilbridge.network.VigilApiClient
import java.time.Instant
import java.util.concurrent.TimeUnit

private const val TAG = "OutboxUploadWorker"
private const val WORK_NAME = "vigil_outbox_upload"
private const val MAX_EVENTS_PER_RUN = 50

class OutboxUploadWorker(
    appContext: Context,
    params: WorkerParameters,
) : CoroutineWorker(appContext, params) {

    override suspend fun doWork(): Result {
        val dao = VigilDatabase.get(applicationContext).syncOutboxDao()

        repeat(MAX_EVENTS_PER_RUN) {
            val item = dao.getNextUploadable() ?: return Result.success()
            when (val result = VigilApiClient.postPayload(item.payloadJson)) {
                UploadResult.Success -> dao.delete(item.eventId)
                is UploadResult.Retryable -> {
                    dao.recordFailure(
                        eventId = item.eventId,
                        attemptedAtMs = Instant.now().toEpochMilli(),
                        error = result.message,
                        status = SyncOutboxStatus.PENDING,
                    )
                    Log.w(TAG, "Retryable upload failure event=${item.eventId}: ${result.message}")
                    return Result.retry()
                }
                is UploadResult.Unauthorized -> {
                    dao.recordFailure(
                        eventId = item.eventId,
                        attemptedAtMs = Instant.now().toEpochMilli(),
                        error = result.message,
                        status = SyncOutboxStatus.AUTH_BLOCKED,
                    )
                    Log.e(TAG, "Upload blocked by authentication for event=${item.eventId}")
                    return Result.failure()
                }
                is UploadResult.PermanentFailure -> {
                    dao.recordFailure(
                        eventId = item.eventId,
                        attemptedAtMs = Instant.now().toEpochMilli(),
                        error = result.message,
                        status = SyncOutboxStatus.DEAD_LETTER,
                    )
                    Log.e(TAG, "Permanent upload failure event=${item.eventId}: ${result.message}")
                }
            }
        }

        return if (dao.pendingCount() > 0) Result.retry() else Result.success()
    }

    companion object {
        fun enqueue(context: Context) {
            val request = OneTimeWorkRequestBuilder<OutboxUploadWorker>()
                .setConstraints(
                    Constraints.Builder()
                        .setRequiredNetworkType(NetworkType.CONNECTED)
                        .build()
                )
                .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 30, TimeUnit.SECONDS)
                .build()

            WorkManager.getInstance(context).enqueueUniqueWork(
                WORK_NAME,
                ExistingWorkPolicy.KEEP,
                request,
            )
        }
    }
}
