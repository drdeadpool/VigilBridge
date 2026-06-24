package com.batman.vigilbridge.data

enum class HealthReadFailureKind {
    PERMISSION,
    IO,
    REMOTE,
    SERVICE_UNAVAILABLE,
    UNKNOWN,
}

data class HealthReadFailure(
    val metric: String,
    val kind: HealthReadFailureKind,
    val message: String?,
) {
    val isRetryable: Boolean
        get() = kind == HealthReadFailureKind.IO ||
            kind == HealthReadFailureKind.REMOTE ||
            kind == HealthReadFailureKind.SERVICE_UNAVAILABLE
}

sealed interface MetricRead<out T> {
    data class Value<T>(val value: T) : MetricRead<T>
    data object NoData : MetricRead<Nothing>
    data class Failure(val error: HealthReadFailure) : MetricRead<Nothing>
}

data class HealthLoadResult(
    val stepsToday: MetricRead<Long>,
    val steps7d: MetricRead<Long>,
    val steps30d: MetricRead<Long>,
    val lastSleep: MetricRead<SleepSummary>,
    val restingHeartRate: MetricRead<Long>,
    val activeEnergy: MetricRead<Double> = MetricRead.NoData,
) {
    private val reads: List<MetricRead<*>>
        get() = listOf(stepsToday, steps7d, steps30d, lastSleep, restingHeartRate, activeEnergy)

    val failures: List<HealthReadFailure>
        get() = reads.mapNotNull { (it as? MetricRead.Failure)?.error }

    val allReadsFailed: Boolean
        get() = reads.all { it is MetricRead.Failure }

    val hasFailures: Boolean
        get() = failures.isNotEmpty()

    val hasRetryableFailures: Boolean
        get() = failures.any { it.isRetryable }

    val dashboard: RawDashboard
        get() = RawDashboard(
            stepsToday = stepsToday.valueOrNull(),
            steps7d = steps7d.valueOrNull(),
            steps30d = steps30d.valueOrNull(),
            lastSleep = lastSleep.valueOrNull(),
            restingHeartRateBpm = restingHeartRate.valueOrNull(),
            activeEnergyKcal = activeEnergy.valueOrNull(),
        )
}

private fun <T> MetricRead<T>.valueOrNull(): T? =
    (this as? MetricRead.Value<T>)?.value
