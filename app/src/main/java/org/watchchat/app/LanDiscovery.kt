package org.watchchat.app

import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import android.net.wifi.WifiManager
import android.os.Handler
import android.os.Looper
import java.util.ArrayDeque

data class ConnectionCandidate(val id:String,val name:String,val url:String,val pin:String,val mode:String="lan")

/** Foreground-only NSD. Serialized resolves also work on older Wear OS releases. */
class LanDiscovery(context:Context,private val found:(ConnectionCandidate)->Unit,private val status:(String)->Unit) {
    private val manager=context.getSystemService(Context.NSD_SERVICE) as NsdManager
    private val connectivity=context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
    private val ui=Handler(Looper.getMainLooper())
    private val lock=(context.applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager).createMulticastLock("watch-chat-scan").apply { setReferenceCounted(false) }
    private val queue=ArrayDeque<NsdServiceInfo>()
    private var running=false;private var resolving=false;private var epoch=0
    private val finish=Runnable { stop();status("扫描结束，可点击重新扫描") }
    private val listener=object:NsdManager.DiscoveryListener {
        override fun onDiscoveryStarted(type:String) {}
        override fun onServiceFound(service:NsdServiceInfo) { ui.post { if(running && service.serviceType.trimEnd('.')=="_watchchat._tcp") { queue.add(service);resolve() } } }
        override fun onServiceLost(service:NsdServiceInfo) {}
        override fun onDiscoveryStopped(type:String) {}
        override fun onStartDiscoveryFailed(type:String,code:Int) { ui.post { if(running) { stop();status("扫描未能开始，请检查Wi-Fi后重试") } } }
        override fun onStopDiscoveryFailed(type:String,code:Int) {}
    }
    fun start() {
        stop();running=true;epoch++
        runCatching { lock.acquire();manager.discoverServices("_watchchat._tcp.",NsdManager.PROTOCOL_DNS_SD,listener);ui.postDelayed(finish,15000) }
            .onFailure { stop();status("请连接Wi-Fi后重试扫描") }
    }
    @Suppress("DEPRECATION") private fun resolve() {
        if(!running || resolving || queue.isEmpty())return
        resolving=true;val requestEpoch=epoch
        val service=queue.removeFirst()
        runCatching { manager.resolveService(service,object:NsdManager.ResolveListener {
            override fun onResolveFailed(info:NsdServiceInfo,code:Int) { ui.post { if(requestEpoch==epoch) { resolving=false;resolve() } } }
            override fun onServiceResolved(info:NsdServiceInfo) { ui.post {
                if(requestEpoch!=epoch || !running)return@post
                resolving=false
                fun attr(key:String)=info.attributes[key]?.toString(Charsets.UTF_8) ?: ""
                val id=attr("id");val pin=attr("pin")
                val subnets=connectivity.allNetworks.filter { connectivity.getNetworkCapabilities(it)?.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)==true }
                    .flatMap { connectivity.getLinkProperties(it)?.linkAddresses ?: emptyList() }
                    .mapNotNull { it.address.hostAddress?.let { address -> address to it.prefixLength } }
                val addresses=(attr("ipv4").split(',')+listOfNotNull(info.host?.hostAddress)).distinct()
                val address=ConnectionAddress.lanAddress(addresses,subnets) ?: ""
                if(id.matches(Regex("[A-Za-z0-9_-]{1,100}")) && pin.matches(Regex("[a-f0-9]{64}")) && address.matches(Regex("[0-9.]+")) && info.port in 1..65535)
                    found(ConnectionCandidate(id,attr("name").take(40).ifBlank { info.serviceName.take(40) },"https://$address:${info.port}",pin))
                resolve()
            } }
        }) }.onFailure { resolving=false;resolve() }
    }
    fun stop() {
        val wasRunning=running;running=false;epoch++;queue.clear();resolving=false;ui.removeCallbacks(finish)
        if(wasRunning)runCatching { manager.stopServiceDiscovery(listener) }
        if(lock.isHeld)lock.release()
    }
}
