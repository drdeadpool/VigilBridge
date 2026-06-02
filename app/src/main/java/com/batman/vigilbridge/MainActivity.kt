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
import androidx.health.connect.client.records.RestingHeartRateRecord
import androidx.health.connect.client.records.SleepSessionRecord
import androidx.health.connect.client.records.StepsRecord
import com.batman.vigilbridge.ui.UnavailableScreen
import com.batman.vigilbridge.ui.VigilScreen
import com.batman.vigilbridge.ui.theme.VigilBridgeTheme
import kotlinx.coroutines.launch

private const val TAG = "MainActivity"

private val PERMISSIONS = setOf(
    HealthPermission.getReadPermission(StepsRecord::class),
    HealthPermission.getReadPermission(SleepSessionRecord::class),
    HealthPermission.getReadPermission(RestingHeartRateRecord::class),
)

class MainActivity : ComponentActivity() {

    private var healthConnectClient: HealthConnectClient? = null
    private var sdkStatus: Int = HealthConnectClient.SDK_UNAVAILABLE

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        sdkStatus = HealthConnectClient.getSdkStatus(this)

        if (sdkStatus == HealthConnectClient.SDK_AVAILABLE) {
            healthConnectClient = HealthConnectClient.getOrCreate(this)
        }

        setContent {
            VigilBridgeTheme {
                Surface {
                    val client = healthConnectClient
                    if (client == null) {
                        UnavailableScreen(sdkStatus)
                    } else {
                        val scope = rememberCoroutineScope()
                        var permissionsGranted by remember { mutableStateOf(false) }

                        val launcher = rememberLauncherForActivityResult(
                            PermissionController.createRequestPermissionResultContract()
                        ) { granted ->
                            Log.d(TAG, "Permissions granted: $granted")
                            permissionsGranted = PERMISSIONS.all { it in granted }
                        }

                        LaunchedEffect(Unit) {
                            try {
                                val granted = client.permissionController.getGrantedPermissions()
                                permissionsGranted = PERMISSIONS.all { it in granted }
                            } catch (e: Exception) {
                                Log.e(TAG, "Permission check failed", e)
                            }
                        }

                        VigilScreen(
                            client = client,
                            permissionsGranted = permissionsGranted,
                            onRequestPermissions = {
                                launcher.launch(PERMISSIONS)
                            },
                            onRecheck = {
                                scope.launch {
                                    try {
                                        val granted = client.permissionController.getGrantedPermissions()
                                        permissionsGranted = PERMISSIONS.all { it in granted }
                                    } catch (e: Exception) {
                                        Log.e(TAG, "Re-check failed", e)
                                    }
                                }
                            }
                        )
                    }
                }
            }
        }
    }
}
