package com.batman.vigilbridge.data

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase
import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase

@Database(
    entities = [VitalsSnapshot::class, SyncOutboxItem::class],
    version = 2,
    exportSchema = false,
)
abstract class VigilDatabase : RoomDatabase() {

    abstract fun vitalsDao(): VitalsDao
    abstract fun syncOutboxDao(): SyncOutboxDao

    companion object {
        @Volatile private var instance: VigilDatabase? = null

        private val MIGRATION_1_2 = object : Migration(1, 2) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL(
                    """
                    CREATE TABLE IF NOT EXISTS sync_outbox (
                        eventId TEXT NOT NULL PRIMARY KEY,
                        payloadJson TEXT NOT NULL,
                        createdAtMs INTEGER NOT NULL,
                        attemptCount INTEGER NOT NULL,
                        lastAttemptAtMs INTEGER,
                        lastError TEXT,
                        status TEXT NOT NULL
                    )
                    """.trimIndent()
                )
                db.execSQL(
                    """
                    CREATE INDEX IF NOT EXISTS index_sync_outbox_status_createdAtMs
                    ON sync_outbox (status, createdAtMs)
                    """.trimIndent()
                )
            }
        }

        fun get(context: Context): VigilDatabase = instance ?: synchronized(this) {
            instance ?: Room.databaseBuilder(
                context.applicationContext,
                VigilDatabase::class.java,
                "vigil.db"
            )
                .addMigrations(MIGRATION_1_2)
                .build()
                .also { instance = it }
        }
    }
}
