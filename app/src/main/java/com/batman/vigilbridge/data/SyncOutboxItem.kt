package com.batman.vigilbridge.data

import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

object SyncOutboxStatus {
    const val PENDING = "pending"
    const val AUTH_BLOCKED = "auth_blocked"
    const val DEAD_LETTER = "dead_letter"
}

@Entity(
    tableName = "sync_outbox",
    indices = [Index(value = ["status", "createdAtMs"])],
)
data class SyncOutboxItem(
    @PrimaryKey val eventId: String,
    val payloadJson: String,
    val createdAtMs: Long,
    val attemptCount: Int = 0,
    val lastAttemptAtMs: Long? = null,
    val lastError: String? = null,
    val status: String = SyncOutboxStatus.PENDING,
)
