package org.watchchat.app

import org.json.JSONObject
import java.net.URL
import java.security.MessageDigest
import java.security.SecureRandom
import java.security.cert.X509Certificate
import java.util.concurrent.TimeUnit
import javax.net.ssl.SSLContext
import javax.net.ssl.TrustManager
import javax.net.ssl.X509TrustManager
import okhttp3.Call
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody

class BridgeClient(
    val url: String, private val token: String, pin: String,
    private val callFactory: Call.Factory? = null,
    val mode: String = "lan"
) {
    private val requestLock = Any()
    private var foreground = true
    private val requests = mutableSetOf<Call>()

    fun setForeground(value: Boolean) {
        val pending=synchronized(requestLock) {
            if(foreground==value)return
            foreground = value
            if(value)return
            requests.toList()
        }
        if(pending.isEmpty() && http.connectionPool.connectionCount()==0)return
        // Android's TLS close can write close_notify. Both cancellation and idle
        // socket eviction must therefore run off the Activity/lifecycle thread.
        Thread({
            pending.forEach { it.cancel() }
            val stillPaused=synchronized(requestLock) { !foreground }
            if(stillPaused)http.connectionPool.evictAll()
        },"bridge-cleanup").apply { isDaemon=true; start() }
    }
    private val expected = pin.lowercase()
    private val host = URL(url).host
    init {
        require(URL(url).protocol == "https") { "连接地址必须使用 https" }
        require(expected.matches(Regex("[0-9a-f]{64}"))) { "证书指纹应为64位" }
        require(mode in listOf("lan","public")) { "连接模式无效" }
        if(mode=="public")ConnectionAddress.publicUrl(url)
    }
    private val trustManager = object : X509TrustManager {
            override fun getAcceptedIssuers(): Array<X509Certificate> = emptyArray()
            override fun checkClientTrusted(chain: Array<X509Certificate>, authType: String) = throw java.security.cert.CertificateException("不支持客户端证书")
            override fun checkServerTrusted(chain: Array<X509Certificate>, authType: String) {
                if (chain.isEmpty()) throw java.security.cert.CertificateException("缺少电脑证书")
                chain[0].checkValidity()
                val actual = MessageDigest.getInstance("SHA-256").digest(chain[0].encoded).joinToString("") { "%02x".format(it) }
                if (!MessageDigest.isEqual(actual.toByteArray(), expected.toByteArray())) {
                    throw java.security.cert.CertificateException("电脑证书不匹配，请重新配对")
                }
            }
    }
    private val socketFactory = SSLContext.getInstance("TLS").apply {
        init(null, arrayOf<TrustManager>(trustManager), SecureRandom())
    }.socketFactory
    private val http = OkHttpClient.Builder()
        .apply {
            if(mode=="lan") {
                sslSocketFactory(socketFactory, trustManager)
                hostnameVerifier { hostname, _ -> hostname == host }
            }
            // Public domains use Android's CA store AND the standard hostname verifier.
        }
        .connectTimeout(8, TimeUnit.SECONDS)
        .readTimeout(15, TimeUnit.SECONDS)
        .callTimeout(25, TimeUnit.SECONDS)
        .followRedirects(false).followSslRedirects(false)
        // Mutating requests must never be retried invisibly after ambiguous delivery.
        .retryOnConnectionFailure(false)
        .build()
    private val voiceHttp = http.newBuilder().readTimeout(90, TimeUnit.SECONDS)
        .callTimeout(100, TimeUnit.SECONDS).build()



    fun bytes(path: String, payload: ByteArray? = null, type: String = "application/json"): ByteArray {
        val request = Request.Builder().url(url.trimEnd('/') + path)
            .header("Authorization", "Bearer $token").apply {
                if (payload != null) post(payload.toRequestBody(type.toMediaType()))
            }.build()
        val transport = callFactory ?: if(path == "/api/speak" || path == "/api/transcribe")voiceHttp else http
        val call = transport.newCall(request)
        synchronized(requestLock) {
            if (!foreground || Thread.currentThread().isInterrupted) {
                call.cancel()
                throw java.io.InterruptedIOException("应用已离开前台")
            }
            requests.add(call)
        }
        try {
            return call.execute().use { response ->
                val body = response.body?.bytes() ?: byteArrayOf()
                if (!response.isSuccessful) {
                    val raw = body.toString(Charsets.UTF_8)
                    val message = runCatching { JSONObject(raw).optString("error", raw) }.getOrDefault(raw)
                    throw IllegalStateException(message.take(250).ifEmpty { "电脑返回错误 ${response.code}" })
                }
                body
            }
        } finally { synchronized(requestLock) { requests.remove(call) } }
    }

    fun json(path: String, payload: JSONObject? = null): JSONObject =
        JSONObject(bytes(path, payload?.toString()?.toByteArray(Charsets.UTF_8)).toString(Charsets.UTF_8))
}
