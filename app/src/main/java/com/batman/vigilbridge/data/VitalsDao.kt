package com.batman.vigilbridge.data

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.Query

@Dao
interface VitalsDao {
    @Insert
    suspend fun insert(snapshot: VitalsSnapshot)

    @Query("SELECT * FROM vitals_snapshots ORDER BY timestampMs DESC LIMIT 1")
    suspend fun getLatest(): VitalsSnapshot?

    @Query("SELECT * FROM vitals_snapshots ORDER BY timestampMs DESC LIMIT :n")
    suspend fun getRecent(n: Int): List<VitalsSnapshot>
}
