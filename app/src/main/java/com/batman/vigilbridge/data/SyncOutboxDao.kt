package com.batman.vigilbridge.data

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query

@Dao
interface SyncOutboxDao {
    @Insert(onConflict = OnConflictStrategy.IGNORE)
    suspend fun insert(item: SyncOutboxItem): Long

    @Query(
        """
        SELECT * FROM sync_outbox
        WHERE status IN ('pending', 'auth_blocked')
        ORDER BY createdAtMs ASC
        LIMIT 1
        """
    )
    suspend fun getNextUploadable(): SyncOutboxItem?

    @Query("DELETE FROM sync_outbox WHERE eventId = :eventId")
    suspend fun delete(eventId: String)

    @Query(
        """
        UPDATE sync_outbox
        SET attemptCount = attemptCount + 1,
            lastAttemptAtMs = :attemptedAtMs,
            lastError = :error,
            status = :status
        WHERE eventId = :eventId
        """
    )
    suspend fun recordFailure(
        eventId: String,
        attemptedAtMs: Long,
        error: String,
        status: String,
    )

    @Query("SELECT COUNT(*) FROM sync_outbox WHERE status = 'pending'")
    suspend fun pendingCount(): Int
}
