package com.batman.vigilbridge

import com.batman.vigilbridge.data.HealthLoadResult
import com.batman.vigilbridge.data.HealthReadFailure
import com.batman.vigilbridge.data.HealthReadFailureKind
import com.batman.vigilbridge.data.MetricRead
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class HealthReadResultTest {

    @Test
    fun `no data is distinct from a failed read`() {
        val result = HealthLoadResult(
            stepsToday = MetricRead.Value(0),
            steps7d = MetricRead.Value(100),
            steps30d = MetricRead.Value(200),
            lastSleep = MetricRead.NoData,
            restingHeartRate = failure(
                metric = "resting_hr",
                kind = HealthReadFailureKind.PERMISSION,
            ),
        )

        assertFalse(result.allReadsFailed)
        assertTrue(result.hasFailures)
        assertEquals(1, result.failures.size)
        assertNull(result.dashboard.lastSleep)
        assertNull(result.dashboard.restingHeartRateBpm)
    }

    @Test
    fun `all transient failures request retry`() {
        val result = HealthLoadResult(
            stepsToday = failure("steps_today", HealthReadFailureKind.IO),
            steps7d = failure("steps_7d", HealthReadFailureKind.REMOTE),
            steps30d = failure(
                "steps_30d",
                HealthReadFailureKind.SERVICE_UNAVAILABLE,
            ),
            lastSleep = failure("sleep", HealthReadFailureKind.REMOTE),
            restingHeartRate = failure("resting_hr", HealthReadFailureKind.IO),
            activeEnergy = failure("active_energy", HealthReadFailureKind.IO),
        )

        assertTrue(result.allReadsFailed)
        assertTrue(result.hasRetryableFailures)
    }

    @Test
    fun `active energy value maps into dashboard`() {
        val result = HealthLoadResult(
            stepsToday = MetricRead.Value(0),
            steps7d = MetricRead.Value(0),
            steps30d = MetricRead.Value(0),
            lastSleep = MetricRead.NoData,
            restingHeartRate = MetricRead.NoData,
            activeEnergy = MetricRead.Value(412.5),
        )

        assertFalse(result.allReadsFailed)
        assertEquals(412.5, result.dashboard.activeEnergyKcal!!, 0.0001)
    }

    @Test
    fun `active energy no-data leaves dashboard null`() {
        val result = HealthLoadResult(
            stepsToday = MetricRead.Value(0),
            steps7d = MetricRead.Value(0),
            steps30d = MetricRead.Value(0),
            lastSleep = MetricRead.NoData,
            restingHeartRate = MetricRead.NoData,
            activeEnergy = MetricRead.NoData,
        )

        assertNull(result.dashboard.activeEnergyKcal)
    }

    private fun failure(
        metric: String,
        kind: HealthReadFailureKind,
    ): MetricRead.Failure = MetricRead.Failure(
        HealthReadFailure(metric = metric, kind = kind, message = "test")
    )
}
