package com.batman.vigilbridge.ui

import android.content.Context
import android.util.Log
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import com.batman.vigilbridge.data.HealthRepository
import com.batman.vigilbridge.data.RawDashboard
import com.batman.vigilbridge.network.VigilApiClient
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter

private const val TAG = "DashboardViewModel"

data class DashboardUiState(
    val isLoading: Boolean = true,
    val stepsToday: String = "—",
    val steps7d: String = "—",
    val steps30d: String = "—",
    val lastSleepDuration: String = "—",
    val lastSleepStart: String = "—",
    val lastSleepEnd: String = "—",
    val restingHeartRate: String = "—",
    val lastSynced: String = "",
    val syncError: String? = null,
)

class DashboardViewModel(
    private val repo: HealthRepository,
    private val context: Context,
) : ViewModel() {

    private val _state = MutableStateFlow(DashboardUiState())
    val state: StateFlow<DashboardUiState> = _state.asStateFlow()

    init { refresh() }

    fun refresh() {
        viewModelScope.launch {
            _state.update { it.copy(isLoading = true, syncError = null) }

            val raw = try {
                repo.load()
            } catch (e: Exception) {
                Log.e(TAG, "HC load failed: ${e.message}")
                _state.update { it.copy(isLoading = false, syncError = "Health Connect unavailable") }
                return@launch
            }

            val posted = VigilApiClient.postSnapshot(context, raw, Instant.now())

            _state.value = raw.toUiState().copy(
                syncError = if (!posted) "Sync failed — check connection" else null,
            )
        }
    }

    private fun RawDashboard.toUiState(): DashboardUiState {
        val zone = ZoneId.systemDefault()
        val dateFmt = DateTimeFormatter.ofPattern("EEE h:mm a").withZone(zone)
        val timeFmt = DateTimeFormatter.ofPattern("h:mm a").withZone(zone)
        val syncFmt = DateTimeFormatter.ofPattern("MMM d, h:mm a").withZone(zone)

        val durationStr = lastSleep?.let {
            "${it.actualSleepMinutes / 60}h ${it.actualSleepMinutes % 60}m"
        } ?: "—"

        return DashboardUiState(
            isLoading = false,
            stepsToday = stepsToday?.let { "%,d".format(it) } ?: "—",
            steps7d = steps7d?.let { "%,d".format(it) } ?: "—",
            steps30d = steps30d?.let { "%,d".format(it) } ?: "—",
            lastSleepDuration = durationStr,
            lastSleepStart = lastSleep?.let { dateFmt.format(it.startTime) } ?: "—",
            lastSleepEnd = lastSleep?.let { timeFmt.format(it.endTime) } ?: "—",
            restingHeartRate = restingHeartRateBpm?.let { "$it bpm" } ?: "—",
            lastSynced = "Synced ${syncFmt.format(Instant.now())}",
        )
    }

    companion object {
        fun factory(repo: HealthRepository, context: Context): ViewModelProvider.Factory = viewModelFactory {
            initializer { DashboardViewModel(repo, context.applicationContext) }
        }
    }
}
