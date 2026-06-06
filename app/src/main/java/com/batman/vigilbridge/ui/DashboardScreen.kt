package com.batman.vigilbridge.ui

import androidx.compose.foundation.layout.*
import androidx.compose.runtime.collectAsState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.health.connect.client.HealthConnectClient
import androidx.lifecycle.viewmodel.compose.viewModel
import com.batman.vigilbridge.data.HealthRepository
import com.batman.vigilbridge.data.VigilDatabase
import com.batman.vigilbridge.sync.SnapshotCaptureStore

@Composable
fun UnavailableScreen(status: Int) {
    val message = when (status) {
        1 -> "Health Connect not installed"
        3 -> "Health Connect needs updating"
        else -> "Health Connect unavailable (status=$status)"
    }
    androidx.compose.foundation.layout.Box(
        modifier = Modifier.fillMaxSize(),
        contentAlignment = Alignment.Center
    ) {
        Text(message, style = MaterialTheme.typography.bodyLarge)
    }
}

@Composable
fun VigilScreen(
    client: HealthConnectClient,
    permissionsGranted: Boolean,
    onRequestPermissions: () -> Unit,
    onRecheck: () -> Unit,
) {
    if (!permissionsGranted) {
        PermissionScreen(onRequest = onRequestPermissions, onRecheck = onRecheck)
        return
    }

    val context = LocalContext.current
    val dependencies = remember(client) {
        val appContext = context.applicationContext
        val database = VigilDatabase.get(appContext)
        HealthRepository(client) to SnapshotCaptureStore(appContext, database)
    }
    val vm = viewModel<DashboardViewModel>(
        factory = DashboardViewModel.factory(
            repo = dependencies.first,
            captureStore = dependencies.second,
        )
    )
    val state by vm.state.collectAsState()

    Dashboard(state = state, onRefresh = vm::refresh)
}

@Composable
private fun PermissionScreen(onRequest: () -> Unit, onRecheck: () -> Unit) {
    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        Column(
            modifier = Modifier.padding(32.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Text("Vigil", style = MaterialTheme.typography.headlineLarge)
            Spacer(Modifier.height(8.dp))
            Text(
                "Health Connect access required",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(Modifier.height(8.dp))
            Button(onClick = onRequest, modifier = Modifier.fillMaxWidth()) {
                Text("Grant Permissions")
            }
            OutlinedButton(onClick = onRecheck, modifier = Modifier.fillMaxWidth()) {
                Text("Re-check Permissions")
            }
        }
    }
}

@Composable
private fun Dashboard(state: DashboardUiState, onRefresh: () -> Unit) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 20.dp, vertical = 24.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text("Vigil", style = MaterialTheme.typography.headlineMedium)
            TextButton(onClick = onRefresh, enabled = !state.isLoading) {
                Text("Refresh")
            }
        }

        if (state.isLoading) {
            LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
        }

        if (state.syncError != null) {
            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(
                    containerColor = MaterialTheme.colorScheme.errorContainer,
                ),
            ) {
                Text(
                    text = state.syncError,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onErrorContainer,
                    modifier = Modifier.padding(horizontal = 16.dp, vertical = 12.dp),
                )
            }
        }

        SectionLabel("Steps")
        MetricCard(label = "Today", value = state.stepsToday)
        MetricCard(label = "Last 7 days", value = state.steps7d)
        MetricCard(label = "Last 30 days", value = state.steps30d)

        SectionLabel("Sleep")
        MetricCard(label = "Duration", value = state.lastSleepDuration)
        MetricCard(label = "Bedtime", value = state.lastSleepStart)
        MetricCard(label = "Wake time", value = state.lastSleepEnd)

        SectionLabel("Heart")
        MetricCard(label = "Resting heart rate", value = state.restingHeartRate)

        if (state.lastSynced.isNotEmpty()) {
            Text(
                text = state.lastSynced,
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(top = 4.dp),
            )
        }
    }
}

@Composable
private fun SectionLabel(text: String) {
    Text(
        text = text,
        style = MaterialTheme.typography.titleSmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        modifier = Modifier.padding(top = 4.dp),
    )
}

@Composable
private fun MetricCard(label: String, value: String) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(horizontal = 16.dp, vertical = 14.dp)) {
            Text(
                text = label.uppercase(),
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(Modifier.height(4.dp))
            Text(
                text = value,
                style = MaterialTheme.typography.headlineSmall,
            )
        }
    }
}
