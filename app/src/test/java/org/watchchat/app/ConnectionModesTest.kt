package org.watchchat.app

import okhttp3.OkHttpClient
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config
import javax.net.ssl.SSLContext

@RunWith(RobolectricTestRunner::class)
@Config(sdk=[30])
class ConnectionModesTest {
    @Test fun discoveryChoosesTheWatchSubnetInsteadOfVirtualAdapters() {
        val addresses=listOf("10.222.222.1","172.26.128.1","192.168.50.10")
        assertEquals("192.168.50.10",ConnectionAddress.lanAddress(addresses,listOf("192.168.50.20" to 24)))
        assertNull(ConnectionAddress.lanAddress(addresses,listOf("192.168.5.8" to 24)))
        assertNull(ConnectionAddress.lanAddress(listOf("192.168.50.999"),listOf("192.168.50.20" to 24)))
        assertNull(ConnectionAddress.lanAddress(addresses,listOf("0.0.0.0" to 0)))
    }
    @Test fun sameComputerAcrossModesRetainsSessionDraftAndPendingRequest() {
        val prefs=RuntimeEnvironment.getApplication().getSharedPreferences("dual-mode-test",0);prefs.edit().clear().commit()
        val store=ComputerProfiles(prefs)
        val lan=ComputerProfile("same-pc","电脑","https://192.168.1.2:8766","token","a".repeat(64),publicUrl="https://watch.example.com")
        store.save(lan);store.putState("sessionId","same-thread");store.putState("draft:same-thread","原草稿");store.putState("pendingId:same-thread","original-request")
        store.save(lan.using("public"))
        val reopened=ComputerProfiles(prefs)
        assertEquals(1,reopened.all().size);assertEquals("public",reopened.active()!!.mode)
        assertEquals("same-thread",reopened.getState("sessionId"));assertEquals("原草稿",reopened.getState("draft:same-thread"))
        assertEquals("original-request",reopened.getState("pendingId:same-thread"))
        reopened.save(reopened.active()!!.using("lan"));assertEquals(lan.url,reopened.active()!!.url)
    }
    @Test fun legacyProfilesDefaultToLanWithoutDiscardingOtherPreferences() {
        val prefs=RuntimeEnvironment.getApplication().getSharedPreferences("dual-mode-legacy",0);prefs.edit().clear().commit()
        prefs.edit().putString("computers","""[{"id":"pc","name":"原电脑","url":"https://192.168.1.2:8766","token":"secret","pin":"${"a".repeat(64)}"}]""").putString("activeComputer","pc").putString("unknown","keep").commit()
        val store=ComputerProfiles(prefs);assertEquals("lan",store.active()!!.mode);assertEquals(store.active()!!.url,store.active()!!.lanUrl)
        assertEquals("keep",prefs.getString("unknown",null));assertThrows(IllegalArgumentException::class.java) { store.active()!!.using("public") }
    }
    @Test fun publicModeUsesStandardHostnameValidationRatherThanLanPinOnlyVerifier() {
        val public=BridgeClient("https://watch.example.com","token","a".repeat(64),mode="public")
        val lan=BridgeClient("https://watch.example.com","token","a".repeat(64))
        fun http(client:BridgeClient)=BridgeClient::class.java.getDeclaredField("http").apply { isAccessible=true }.get(client) as OkHttpClient
        val unverified=SSLContext.getDefault().createSSLEngine().session
        assertFalse(http(public).hostnameVerifier.verify("watch.example.com",unverified))
        assertTrue(http(lan).hostnameVerifier.verify("watch.example.com",unverified))
    }
    @Test fun publicAddressOnlyAcceptsHttpsOriginsAndNeverEmbeddedCredentials() {
        assertEquals("https://watch.example.com",ConnectionAddress.publicUrl("WATCH.example.com/"))
        for(value in listOf("http://watch.example.com","https://127.0.0.1","https://user:pass@watch.example.com","https://watch.example.com/path","https://watch.example.com:8766","https://watch.local"))
            assertThrows(IllegalArgumentException::class.java) { ConnectionAddress.publicUrl(value) }
    }
    @Test fun verificationCodeChangesIfEndpointOrIdentityChanges() {
        val code=ConnectionAddress.code("pc","a".repeat(64),"lan","https://192.168.1.2:8766","request-1234567890","b".repeat(64))
        assertTrue(code.matches(Regex("[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{4}")))
        assertNotEquals(code,ConnectionAddress.code("pc","a".repeat(64),"public","https://evil.example","request-1234567890","b".repeat(64)))
    }
}
