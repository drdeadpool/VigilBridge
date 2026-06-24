package com.batman.vigilbridge.data

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "vitals_snapshots")
data class VitalsSnapshot(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val timestampMs: Long,
    val stepsToday: Long?,
    val steps7d: Long?,
    val steps30d: Long?,
    val sleepDurationMinutes: Long?,
    val sleepStartMs: Long?,
    val sleepEndMs: Long?,
    val restingHrBpm: Long?,
    val activeEnergyKcal: Double?,
)
