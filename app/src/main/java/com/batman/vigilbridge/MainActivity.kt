package com.batman.vigilbridge

import android.os.Bundle
import android.util.Log
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.compose.material3.Surface
import androidx.compose.runtime.*
import androidx.health.connect.client.HealthConnectClient
import androidx.health.connect.client.PermissionController
import androidx.health.connect.client.permission.HealthPermission
import androidx.health.connect.client.records.HeartRateRecord
import androidx.health.connect.client.records.RestingHeartRateRecord
import androidx.health.connect.client.records.SleepSessionRecord
import androidx.health.connect.client.records.StepsRecord
import androidx.lifecycle.lifecycleScope
import com.batman.vigilbridge.ui.UnavailableScreen
import com.batman.vigilbridge.ui.VigilScreen
import com.batman.vigilbridge.ui.theme.VigilBridgeTheme
import com.batman.vigilbridge.work.VitalsSyncWorker
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.launch

private const val TAG = "MainActivity"

private val PERMISSIONS = setOf(
    HealthPermission.getReadPermission(StepsRecord::class),
    HealthPermission.getReadPermission(SleepSessionRecord::class),
    HealthPermission.getReadPermission(RestingHeartRateRecord::class),
    HealthPermission.getReadPermission(HeartRateRecord::class),
    HealthPermission.PERMISSION_READ_HEALTH_DATA_IN_BACKGROUND,
)

class MainActivity : ComponentActivity() {

    private var healthConnectClient: HealthConnectClient? = null
    private var sdkStatus: Int = HealthConnectClient.SDK_UNAVAILABLE

    // Hoisted outside setContent so onResume() can write to it.
    private val permissionsGranted = mutableStateOf(false)

    override fun onResume() {
        super.onResume()
        val client = healthConnectClient ?: return
        lifecycleScope.launch {
            try {
                val granted = client.permissionController.getGrantedPermissions()
                permissionsGranted.value = PERMISSIONS.all { it in granted }
                Log.d(TAG, "onResume permission recheck: allGranted=${permissionsGranted.value}")
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                Log.e(TAG, "onResume permission check failed", e)
            }
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        sdkStatus = HealthConnectClient.getSdkStatus(this)

        if (sdkStatus == HealthConnectClient.SDK_AVAILABLE) {
            healthConnectClient = HealthConnectClient.getOrCreate(this)
            VitalsSyncWorker.schedule(this)
        }

        setContent {
            VigilBridgeTheme {
                Surface {
                    val client = healthConnectClient
                    if (client == null) {
                        UnavailableScreen(sdkStatus)
                    } else {
                        val granted by permissionsGranted

                        val launcher = rememberLauncherForActivityResult(
                            PermissionController.createRequestPermissionResultContract()
                        ) { grantedPerms ->
                            Log.d(TAG, "Permission dialog result: $grantedPerms")
                            permissionsGranted.value = PERMISSIONS.all { it in grantedPerms }
                        }

                        VigilScreen(
                            client = client,
                            permissionsGranted = granted,
                            onRequestPermissions = {
                                launcher.launch(PERMISSIONS)
                            },
                            onRecheck = {
                                lifecycleScope.launch {
                                    try {
                                        val g = client.permissionController.getGrantedPermissions()
                                        permissionsGranted.value = PERMISSIONS.all { it in g }
                                    } catch (e: CancellationException) {
                                        throw e
                                    } catch (e: Exception) {
                                        Log.e(TAG, "Manual recheck failed", e)
                                    }
                                }
                            },
                        )
                    }
                }
            }
        }
    }
}
