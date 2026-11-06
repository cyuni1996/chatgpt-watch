package org.watchchat.app

/** Foreground only. Delay starts after the previous request finishes. */
object PollPolicy {
    fun delayMillis(active: Boolean, panelOpen: Boolean, failures: Int): Long = when {
        failures > 0 -> minOf(30_000L, 2_000L shl minOf(failures - 1, 4))
        active -> 1_200L
        panelOpen -> 10_000L
        else -> 5_000L
    }
}
