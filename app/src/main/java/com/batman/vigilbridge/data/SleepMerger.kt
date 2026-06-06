package com.batman.vigilbridge.data

import java.time.Instant

data class SleepSummary(
    val startTime: Instant,
    val endTime: Instant,
    val actualSleepMinutes: Long,
    val timeInBedMinutes: Long,
    val sessionCount: Int,
)

internal data class RawSleepSession(
    val startSeconds: Long,
    val endSeconds: Long,
    val stages: List<RawSleepStage>,
)

internal data class RawSleepStage(
    val startSeconds: Long,
    val endSeconds: Long,
    val stageType: Int,
)

// Mirror of SleepSessionRecord.STAGE_TYPE_* constants (stable HC SDK API values)
internal const val STAGE_AWAKE       = 1
internal const val STAGE_OUT_OF_BED  = 3
internal const val STAGE_LIGHT       = 4
internal const val STAGE_DEEP        = 5
internal const val STAGE_REM         = 6

private val AWAKE_TYPES = setOf(STAGE_AWAKE, STAGE_OUT_OF_BED)
private const val MIN_ACTUAL_SLEEP_SECONDS = 3L * 3600L  // discard naps < 3h actual sleep

/**
 * Merges consecutive sleep sessions with gaps <= gapToleranceSeconds into a single sleep block,
 * matching Samsung Health's display model. Returns the block with the most actual sleep,
 * or null if nothing qualifies.
 *
 * "Actual sleep" = sum of non-AWAKE/non-OUT_OF_BED stage durations across all merged sessions.
 * Sessions with no stages are counted as fully asleep (conservative assumption).
 *
 * INV-001 verified: sessions 01:48–06:21 and 06:31–08:07 (10-min gap) merge to
 * actual_sleep=342min and time_in_bed=379min, matching Samsung Health exactly.
 */
internal fun mergeSleepSessions(
    sessions: List<RawSleepSession>,
    gapToleranceSeconds: Long = 30L * 60L,
): SleepSummary? {
    if (sessions.isEmpty()) return null

    val sorted = sessions.sortedBy { it.startSeconds }
    val groups = mutableListOf<MutableList<RawSleepSession>>()
    var current = mutableListOf(sorted[0])

    for (i in 1 until sorted.size) {
        val gap = sorted[i].startSeconds - current.last().endSeconds
        if (gap <= gapToleranceSeconds) {
            current.add(sorted[i])
        } else {
            groups.add(current)
            current = mutableListOf(sorted[i])
        }
    }
    groups.add(current)

    val best = groups.maxByOrNull { group -> actualSleepSeconds(group) } ?: return null
    val totalActual = actualSleepSeconds(best)
    if (totalActual < MIN_ACTUAL_SLEEP_SECONDS) return null

    val mergedStart = best.first().startSeconds
    val mergedEnd   = best.last().endSeconds

    return SleepSummary(
        startTime          = Instant.ofEpochSecond(mergedStart),
        endTime            = Instant.ofEpochSecond(mergedEnd),
        actualSleepMinutes = totalActual / 60L,
        timeInBedMinutes   = (mergedEnd - mergedStart) / 60L,
        sessionCount       = best.size,
    )
}

private fun actualSleepSeconds(group: List<RawSleepSession>): Long =
    group.sumOf { s ->
        if (s.stages.isEmpty()) {
            s.endSeconds - s.startSeconds
        } else {
            s.stages
                .filter { it.stageType !in AWAKE_TYPES }
                .sumOf { it.endSeconds - it.startSeconds }
        }
    }
