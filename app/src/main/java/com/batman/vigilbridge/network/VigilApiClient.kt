package com.batman.vigilbridge.network

import android.content.Context
import android.os.Build
import android.provider.Settings
import android.util.Log
import com.batman.vigilbridge.BuildConfig
import com.batman.vigilbridge.data.RawDashboard
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.time.Instant
import java.time.ZoneId
import java.util.concurrent.TimeUnit

private const val TAG = "VigilApiClient"
private val JSON_MEDIA = "application/json".toMediaType()

sealed interface UploadResult {
    data object Success : UploadResult
    data class Retryable(val message: String) : UploadResult
    data class Unauthorized(val message: String) : UploadResult
    data class PermanentFailure(val message: String) : UploadResult
}

object VigilApiClient {

    private val client = OkHttpClient.Builder()
        .connectTimeout(20, TimeUnit.SECONDS)
        .readTimeout(75, TimeUnit.SECONDS)
        .callTimeout(90, TimeUnit.SECONDS)
        .build()

    fun buildSnapshotPayload(
        context: Context,
        raw: RawDashboard,
        timestamp: Instant,
        eventId: String,
    ): String {
        val androidId = Settings.Secure.getString(
            context.contentResolver,
            Settings.Secure.ANDROID_ID,
        )

        val payload = JSONObject().apply {
            put("record_type", "snapshot")
            put("payloadVersion", 3)
            put("timestampMs", timestamp.toEpochMilli())
            put("timezone", ZoneId.systemDefault().id)
            raw.stepsToday?.let { put("stepsToday", it) }
            raw.steps7d?.let { put("steps7d", it) }
            raw.steps30d?.let { put("steps30d", it) }
            raw.lastSleep?.let { sleep ->
                put("sleepStartMs", sleep.startTime.toEpochMilli())
                put("sleepEndMs", sleep.endTime.toEpochMilli())
                put("actualSleepMinutes", sleep.actualSleepMinutes)
                put("timeInBedMinutes", sleep.timeInBedMinutes)
                put("sleepSessionsCount", sleep.sessionCount)
            }
            raw.restingHeartRateBpm?.let { put("restingHrBpm", it) }
            raw.activeEnergyKcal?.let { put("activeEnergyKcal", it) }
        }

        return JSONObject().apply {
            put("event_id", eventId)
            put("user_external_id", androidId)
            put("device_identifier", Build.MODEL)
            put("device_model", Build.MODEL)
            put("platform", "android")
            put("source_app", "health_connect")
            put("payload", payload)
        }.toString()
    }

    suspend fun postPayload(body: String): UploadResult = withContext(Dispatchers.IO) {
        Log.d(TAG, "POST /ingest payload=${body.length} bytes")

        val request = Request.Builder()
            .url("${BuildConfig.VIGIL_BASE_URL}/ingest")
            .addHeader("X-Api-Key", BuildConfig.INGEST_API_KEY)
            .post(body.toRequestBody(JSON_MEDIA))
            .build()

        try {
            client.newCall(request).execute().use { response ->
                val responseBody = response.body?.string() ?: ""
                Log.d(TAG, "POST /ingest status=${response.code} body=$responseBody")
                when {
                    response.isSuccessful -> UploadResult.Success
                    response.code == 401 || response.code == 403 ->
                        UploadResult.Unauthorized("HTTP ${response.code}")
                    response.code == 408 || response.code == 425 ||
                        response.code == 429 || response.code >= 500 ->
                        UploadResult.Retryable("HTTP ${response.code}")
                    else -> UploadResult.PermanentFailure("HTTP ${response.code}")
                }
            }
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            Log.e(TAG, "POST /ingest exception", e)
            UploadResult.Retryable(e.message ?: e.javaClass.simpleName)
        }
    }
}
