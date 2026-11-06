package org.watchchat.app

import okhttp3.Call
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import org.json.JSONObject
import java.util.concurrent.TimeUnit

internal object ReleaseUpdates {
    private const val ENDPOINT = "https://api.github.com/repos/cyuni1996/chatgpt-watch/releases/latest"
    private const val MAX_RESPONSE_BYTES = 256 * 1024L
    private val versionPattern = Regex("v?(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)")
    private val http = OkHttpClient.Builder()
        .callTimeout(6,TimeUnit.SECONDS)
        .followRedirects(false)
        .retryOnConnectionFailure(false)
        .build()

    fun request(): Call = http.newCall(Request.Builder().url(ENDPOINT)
        .header("Accept","application/vnd.github+json")
        .header("User-Agent","WatchChat-UpdateCheck")
        .build())

    fun newerVersion(response: Response, installed: String): String? {
        if (!response.isSuccessful) return null
        val source = response.body?.source() ?: return null
        if (source.request(MAX_RESPONSE_BYTES + 1)) return null
        return newerVersion(JSONObject(source.readUtf8()),installed)
    }

    fun newerVersion(release: JSONObject, installed: String): String? {
        if (release.optBoolean("draft") || release.optBoolean("prerelease")) return null
        val current = versionParts(installed) ?: return null
        val latest = versionParts(release.optString("tag_name")) ?: return null
        val difference = latest.indices.firstOrNull { latest[it] != current[it] } ?: return null
        return latest.joinToString(".").takeIf { latest[difference] > current[difference] }
    }

    private fun versionParts(value: String): List<Int>? {
        val match = versionPattern.matchEntire(value) ?: return null
        return match.groupValues.drop(1).map { it.toIntOrNull() ?: return null }
    }
}
