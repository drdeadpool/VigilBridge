package com.batman.vigilbridge.work

import android.content.Context
import android.util.Log
import androidx.health.connect.client.HealthConnectClient
import androidx.health.connect.client.permission.HealthPermission
import androidx.health.connect.client.records.RestingHeartRateRecord
import androidx.health.connect.client.records.SleepSessionRecord
import androidx.health.connect.client.records.StepsRecord
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import com.batman.vigilbridge.data.HealthRepository
import com.batman.vigilbridge.data.VigilDatabase
import java.util.concurrent.TimeUnit

private const val TAG = "VitalsSyncWorker"
private const val WORK_NAME = "vigil_vitals_sync"

private val REQUIRED_PERMISSIONS = setOf(
    HealthPermission.getReadPermission(StepsRecord::class),
    HealthPermission.getReadPermission(SleepSessionRecord::class),
    HealthPermission.getReadPermission(RestingHeartRateRecord::class),
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
        } catch (e: Exception) {
            Log.e(TAG, "Permission check failed: ${e.message}")
            return Result.retry()
        }

        if (!REQUIRED_PERMISSIONS.all { it in granted }) {
            return Result.success()
        }

        return try {
            val dao = VigilDatabase.get(applicationContext).vitalsDao()
            val repo = HealthRepository(client, dao)
            repo.load()
            Log.d(TAG, "Background sync complete")
            Result.success()
        } catch (e: Exception) {
            Log.e(TAG, "Background sync failed: ${e.message}")
            Result.retry()
        }
    }

    companion object {
        fun schedule(context: Context) {
            val request = PeriodicWorkRequestBuilder<VitalsSyncWorker>(15, TimeUnit.MINUTES)
                .setConstraints(Constraints.Builder().build())
                .build()

            WorkManager.getInstance(context).enqueueUniquePeriodicWork(
                WORK_NAME,
                ExistingPeriodicWorkPolicy.KEEP,
                request,
            )
        }
    }
}
