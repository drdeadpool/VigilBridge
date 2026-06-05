package com.batman.vigilbridge.network

import android.content.Context
import android.os.Build
import android.provider.Settings
import android.util.Log
import com.batman.vigilbridge.BuildConfig
import com.batman.vigilbridge.data.RawDashboard
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.time.Instant
import java.util.concurrent.TimeUnit

private const val TAG = "VigilApiClient"
private val JSON_MEDIA = "application/json".toMediaType()

object VigilApiClient {

    private val client = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(15, TimeUnit.SECONDS)
        .build()

    suspend fun postSnapshot(
        context: Context,
        raw: RawDashboard,
        timestamp: Instant,
    ): Boolean = withContext(Dispatchers.IO) {
        val androidId = Settings.Secure.getString(
            context.contentResolver,
            Settings.Secure.ANDROID_ID,
        )

        val payload = JSONObject().apply {
            put("record_type", "snapshot")
            put("timestampMs", timestamp.toEpochMilli())
            raw.stepsToday?.let { put("stepsToday", it) }
            raw.steps7d?.let { put("steps7d", it) }
            raw.steps30d?.let { put("steps30d", it) }
            raw.lastSleep?.let { sleep ->
                put("sleepDurationMinutes",
                    (sleep.endTime.epochSecond - sleep.startTime.epochSecond) / 60)
            }
            raw.restingHeartRateBpm?.let { put("restingHrBpm", it) }
        }

        val body = JSONObject().apply {
            put("user_external_id", androidId)
            put("device_identifier", Build.MODEL)
            put("device_model", Build.MODEL)
            put("platform", "android")
            put("source_app", "health_connect")
            put("payload", payload)
        }.toString()

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
                response.isSuccessful
            }
        } catch (e: Exception) {
            Log.e(TAG, "POST /ingest exception: ${e.message}")
            false
        }
    }
}
