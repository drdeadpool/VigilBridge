package com.batman.vigilbridge.ui

import android.util.Log
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import com.batman.vigilbridge.data.HealthRepository
import com.batman.vigilbridge.data.RawDashboard
import com.batman.vigilbridge.sync.SnapshotCaptureStore
import kotlinx.coroutines.CancellationException
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
    private val captureStore: SnapshotCaptureStore,
) : ViewModel() {

    private val _state = MutableStateFlow(DashboardUiState())
    val state: StateFlow<DashboardUiState> = _state.asStateFlow()

    init { refresh() }

    fun refresh() {
        viewModelScope.launch {
            _state.update { it.copy(isLoading = true, syncError = null) }

            val load = try {
                repo.load()
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                Log.e(TAG, "HC load failed", e)
                _state.update { it.copy(isLoading = false, syncError = "Health Connect unavailable") }
                return@launch
            }

            if (load.allReadsFailed) {
                Log.e(TAG, "All Health Connect reads failed: ${load.failures}")
                _state.update {
                    it.copy(
                        isLoading = false,
                        syncError = "Health Connect reads failed",
                    )
                }
                return@launch
            }

            val capturedAt = Instant.now()
            try {
                captureStore.persistAndEnqueue(load.dashboard, capturedAt)
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                Log.e(TAG, "Local capture failed", e)
                _state.update {
                    it.copy(isLoading = false, syncError = "Could not queue local snapshot")
                }
                return@launch
            }

            _state.value = load.dashboard.toUiState(capturedAt).copy(
                syncError = if (load.hasFailures) {
                    "Some Health Connect metrics could not be read"
                } else {
                    null
                },
            )
        }
    }

    private fun RawDashboard.toUiState(capturedAt: Instant): DashboardUiState {
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
            lastSynced = "Captured ${syncFmt.format(capturedAt)}",
        )
    }

    companion object {
        fun factory(
            repo: HealthRepository,
            captureStore: SnapshotCaptureStore,
        ): ViewModelProvider.Factory = viewModelFactory {
            initializer { DashboardViewModel(repo, captureStore) }
        }
    }
}
