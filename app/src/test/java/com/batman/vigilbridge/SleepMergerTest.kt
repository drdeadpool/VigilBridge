package com.batman.vigilbridge

import com.batman.vigilbridge.data.RawSleepSession
import com.batman.vigilbridge.data.RawSleepStage
import com.batman.vigilbridge.data.STAGE_AWAKE
import com.batman.vigilbridge.data.STAGE_DEEP
import com.batman.vigilbridge.data.STAGE_LIGHT
import com.batman.vigilbridge.data.STAGE_OUT_OF_BED
import com.batman.vigilbridge.data.STAGE_REM
import com.batman.vigilbridge.data.mergeSleepSessions
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Test

/**
 * INV-001: Samsung Health vs Health Connect sleep model.
 *
 * Samsung Health splits 2026-06-06 night into two SleepSessionRecords:
 *   Session 1: 01:48–06:21 IST (273 min total, 690s AWAKE → 15690s actual sleep)
 *   Session 2: 06:31–08:07 IST (96 min total,  900s AWAKE → 4860s actual sleep)
 *   Gap: 10 min (600s)
 *
 * Expected merged output:
 *   actualSleepMinutes = (15690 + 4860) / 60 = 342 min = 5h42m  ← matches Samsung Health
 *   timeInBedMinutes   = (16380 + 600 + 5760) / 60 = 379 min = 6h19m ← matches Samsung Health
 *   sessionCount       = 2
 */
class SleepMergerTest {

    // Base epoch seconds — arbitrary; tests use relative offsets
    private val BASE = 1_000_000L

    private fun session1(): RawSleepSession {
        // 273 min = 16380s total. AWAKE = 690s. Actual sleep = 15690s.
        val s = BASE
        return RawSleepSession(
            startSeconds = s,
            endSeconds = s + 16380L,
            stages = listOf(
                RawSleepStage(s,          s + 7690L,  STAGE_LIGHT),   // 7690s LIGHT
                RawSleepStage(s + 7690L,  s + 8380L,  STAGE_AWAKE),   // 690s AWAKE
                RawSleepStage(s + 8380L,  s + 14680L, STAGE_DEEP),    // 6300s DEEP
                RawSleepStage(s + 14680L, s + 16380L, STAGE_REM),     // 1700s REM
            ),
        )
    }

    private fun session2(): RawSleepSession {
        // 96 min = 5760s total. AWAKE = 900s. Actual sleep = 4860s. Gap after session1 = 600s.
        val s = BASE + 16380L + 600L   // 10-min gap
        return RawSleepSession(
            startSeconds = s,
            endSeconds = s + 5760L,
            stages = listOf(
                RawSleepStage(s,          s + 2430L,  STAGE_LIGHT),   // 2430s LIGHT
                RawSleepStage(s + 2430L,  s + 3330L,  STAGE_AWAKE),   // 900s AWAKE
                RawSleepStage(s + 3330L,  s + 5760L,  STAGE_REM),     // 2430s REM
            ),
        )
    }

    // ── Core INV-001 scenario ──────────────────────────────────────────────────

    @Test
    fun `INV-001 two sessions with 10-min gap merge into one`() {
        val result = mergeSleepSessions(listOf(session1(), session2()))
        assertNotNull(result)
        assertEquals(2, result!!.sessionCount)
    }

    @Test
    fun `INV-001 actualSleepMinutes matches Samsung Health 5h42m`() {
        val result = mergeSleepSessions(listOf(session1(), session2()))!!
        // 15690 + 4860 = 20550s / 60 = 342 min (integer division)
        assertEquals(342L, result.actualSleepMinutes)
    }

    @Test
    fun `INV-001 timeInBedMinutes matches Samsung Health 6h19m`() {
        val result = mergeSleepSessions(listOf(session1(), session2()))!!
        // session1(16380) + gap(600) + session2(5760) = 22740s / 60 = 379 min
        assertEquals(379L, result.timeInBedMinutes)
    }

    @Test
    fun `INV-001 startTime is session1 start`() {
        val result = mergeSleepSessions(listOf(session1(), session2()))!!
        assertEquals(BASE, result.startTime.epochSecond)
    }

    @Test
    fun `INV-001 endTime is session2 end`() {
        val result = mergeSleepSessions(listOf(session1(), session2()))!!
        assertEquals(BASE + 16380L + 600L + 5760L, result.endTime.epochSecond)
    }

    // ── Gap tolerance boundary ─────────────────────────────────────────────────

    @Test
    fun `gap exactly at tolerance (1800s) still merges`() {
        val s2 = RawSleepSession(
            startSeconds = BASE + 16380L + 1800L,  // gap = 1800s = 30 min exactly
            endSeconds   = BASE + 16380L + 1800L + 5760L,
            stages = session2().stages.map {
                it.copy(
                    startSeconds = it.startSeconds - session2().startSeconds + BASE + 16380L + 1800L,
                    endSeconds   = it.endSeconds   - session2().startSeconds + BASE + 16380L + 1800L,
                )
            },
        )
        val result = mergeSleepSessions(listOf(session1(), s2))
        assertNotNull(result)
        assertEquals(2, result!!.sessionCount)
    }

    @Test
    fun `gap exceeding tolerance (1801s) does not merge`() {
        val s2 = RawSleepSession(
            startSeconds = BASE + 16380L + 1801L,  // gap = 1801s > 30 min
            endSeconds   = BASE + 16380L + 1801L + 5760L,
            stages = listOf(
                RawSleepStage(BASE + 16380L + 1801L, BASE + 16380L + 1801L + 5760L, STAGE_LIGHT)
            ),
        )
        // session1 has 15690s actual sleep, exceeds 3h min → selected as best group
        val result = mergeSleepSessions(listOf(session1(), s2))
        assertNotNull(result)
        assertEquals(1, result!!.sessionCount)
        assertEquals(BASE, result.startTime.epochSecond)
    }

    // ── Input edge cases ───────────────────────────────────────────────────────

    @Test
    fun `empty input returns null`() {
        assertNull(mergeSleepSessions(emptyList()))
    }

    @Test
    fun `single session below 3h threshold returns null`() {
        val nap = RawSleepSession(
            startSeconds = BASE,
            endSeconds   = BASE + 7200L,  // 2h total
            stages = listOf(
                RawSleepStage(BASE, BASE + 6600L, STAGE_LIGHT),   // 110min sleep
                RawSleepStage(BASE + 6600L, BASE + 7200L, STAGE_AWAKE),
            ),
        )
        assertNull(mergeSleepSessions(listOf(nap)))
    }

    @Test
    fun `single qualifying session returns it as-is`() {
        val result = mergeSleepSessions(listOf(session1()))
        assertNotNull(result)
        assertEquals(1, result!!.sessionCount)
        assertEquals(15690L / 60L, result.actualSleepMinutes)  // 261 min
    }

    @Test
    fun `OUT_OF_BED stages excluded from actual sleep`() {
        val s = BASE
        val session = RawSleepSession(
            startSeconds = s,
            endSeconds   = s + 14400L,  // 4h
            stages = listOf(
                RawSleepStage(s,          s + 10800L, STAGE_DEEP),        // 3h sleep
                RawSleepStage(s + 10800L, s + 12600L, STAGE_OUT_OF_BED), // 30min out of bed
                RawSleepStage(s + 12600L, s + 14400L, STAGE_REM),         // 30min sleep
            ),
        )
        val result = mergeSleepSessions(listOf(session))
        assertNotNull(result)
        // actual = 10800 + 1800 = 12600s / 60 = 210 min (OUT_OF_BED excluded)
        assertEquals(210L, result!!.actualSleepMinutes)
    }

    @Test
    fun `session with no stages counts total duration as actual sleep`() {
        val s = BASE
        val session = RawSleepSession(
            startSeconds = s,
            endSeconds   = s + 18000L,  // 5h, no stages
            stages       = emptyList(),
        )
        val result = mergeSleepSessions(listOf(session))
        assertNotNull(result)
        assertEquals(300L, result!!.actualSleepMinutes)  // 18000/60 = 300 min
    }

    @Test
    fun `best group selected when multiple non-merging groups exist`() {
        // Long nap (but < 3h actual) followed by full night (> 3h actual) with big gap
        val napStart = BASE - 4L * 3600L
        val nap = RawSleepSession(
            startSeconds = napStart,
            endSeconds   = napStart + 5400L,   // 90 min - below threshold
            stages = listOf(
                RawSleepStage(napStart, napStart + 5400L, STAGE_LIGHT)
            ),
        )
        val fullNight = session1()  // 261 min actual sleep — above threshold
        val result = mergeSleepSessions(listOf(nap, fullNight))  // gap > 30 min between them
        assertNotNull(result)
        assertEquals(1, result!!.sessionCount)
        assertEquals(BASE, result.startTime.epochSecond)  // full night selected
    }
}
