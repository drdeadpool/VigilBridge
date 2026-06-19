package com.batman.vigilbridge.work

import android.content.Context
import android.util.Log
import androidx.health.connect.client.HealthConnectClient
import androidx.health.connect.client.permission.HealthPermission
import androidx.health.connect.client.records.HeartRateRecord
import androidx.health.connect.client.records.RestingHeartRateRecord
import androidx.health.connect.client.records.SleepSessionRecord
import androidx.health.connect.client.records.StepsRecord
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import com.batman.vigilbridge.data.HealthRepository
import com.batman.vigilbridge.data.VigilDatabase
import com.batman.vigilbridge.sync.SnapshotCaptureStore
import kotlinx.coroutines.CancellationException
import java.time.Instant
import java.util.concurrent.TimeUnit

private const val TAG = "VitalsSyncWorker"
private const val WORK_NAME = "vigil_vitals_sync"

private val REQUIRED_PERMISSIONS = setOf(
    HealthPermission.getReadPermission(StepsRecord::class),
    HealthPermission.getReadPermission(SleepSessionRecord::class),
    HealthPermission.getReadPermission(RestingHeartRateRecord::class),
    HealthPermission.getReadPermission(HeartRateRecord::class),
    HealthPermission.PERMISSION_READ_HEALTH_DATA_IN_BACKGROUND,
)

class VitalsSyncWorker(
    appContext: Context,
    params: WorkerParameters,
) : CoroutineWorker(appContext, params) {

    override suspend fun doWork(): Result {
        val sdkStatus = HealthConnectClient.getSdkStatus(applicationContext)
        if (sdkStatus != HealthConnectClient.SDK_AVAILABLE) {
            return Result.success()
        }

        val client = HealthConnectClient.getOrCreate(applicationContext)

        val granted = try {
            client.permissionController.getGrantedPermissions()
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            Log.e(TAG, "Permission check failed: ${e.message}")
            return Result.retry()
        }

        if (!REQUIRED_PERMISSIONS.all { it in granted }) {
            return Result.success()
        }

        return try {
            val database = VigilDatabase.get(applicationContext)
            val repo = HealthRepository(client)
            val timestamp = Instant.now()
            val load = repo.load()

            if (load.allReadsFailed) {
                Log.e(TAG, "All Health Connect reads failed: ${load.failures}")
                return if (load.hasRetryableFailures) Result.retry() else Result.failure()
            }

            SnapshotCaptureStore(applicationContext, database)
                .persistAndEnqueue(load.dashboard, timestamp)
            Log.d(TAG, "Background capture queued; partialFailures=${load.failures.size}")
            Result.success()
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            Log.e(TAG, "Background sync failed: ${e.message}")
            Result.retry()
        }
    }

    companion object {
        fun schedule(context: Context) {
            val request = PeriodicWorkRequestBuilder<VitalsSyncWorker>(15, TimeUnit.MINUTES)
                .build()

            WorkManager.getInstance(context).enqueueUniquePeriodicWork(
                WORK_NAME,
                ExistingPeriodicWorkPolicy.UPDATE,
                request,
            )
            OutboxUploadWorker.enqueue(context)
        }
    }
}
