package com.batman.vigilbridge.data

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase

@Database(entities = [VitalsSnapshot::class], version = 1, exportSchema = false)
abstract class VigilDatabase : RoomDatabase() {

    abstract fun vitalsDao(): VitalsDao

    companion object {
        @Volatile private var instance: VigilDatabase? = null

        fun get(context: Context): VigilDatabase = instance ?: synchronized(this) {
            instance ?: Room.databaseBuilder(
                context.applicationContext,
                VigilDatabase::class.java,
                "vigil.db"
            ).build().also { instance = it }
        }
    }
}
