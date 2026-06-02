package com.batman.vigilbridge.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import com.batman.vigilbridge.data.HealthRepository
import com.batman.vigilbridge.data.RawDashboard
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter

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
)

class DashboardViewModel(private val repo: HealthRepository) : ViewModel() {

    private val _state = MutableStateFlow(DashboardUiState())
    val state: StateFlow<DashboardUiState> = _state.asStateFlow()

    init { refresh() }

    fun refresh() {
        viewModelScope.launch {
            _state.update { it.copy(isLoading = true) }
            _state.value = repo.load().toUiState()
        }
    }

    private fun RawDashboard.toUiState(): DashboardUiState {
        val zone = ZoneId.systemDefault()
        val dateFmt = DateTimeFormatter.ofPattern("EEE h:mm a").withZone(zone)
        val timeFmt = DateTimeFormatter.ofPattern("h:mm a").withZone(zone)
        val syncFmt = DateTimeFormatter.ofPattern("MMM d, h:mm a").withZone(zone)

        val durationStr = lastSleep?.let {
            val mins = (it.endTime.epochSecond - it.startTime.epochSecond) / 60
            "${mins / 60}h ${mins % 60}m"
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
        fun factory(repo: HealthRepository): ViewModelProvider.Factory = viewModelFactory {
            initializer { DashboardViewModel(repo) }
        }
    }
}
