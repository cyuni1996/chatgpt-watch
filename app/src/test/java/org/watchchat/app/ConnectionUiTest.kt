package org.watchchat.app

import android.view.View
import android.view.ViewGroup
import android.widget.TextView
import org.junit.Assert.*
import org.junit.Before
import org.junit.After
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk=[30])
class ConnectionUiTest {
    private lateinit var controller:org.robolectric.android.controller.ActivityController<MainActivity>
    private lateinit var activity:MainActivity
    @Before fun start() {
        android.provider.Settings.Global.putFloat(RuntimeEnvironment.getApplication().contentResolver,android.provider.Settings.Global.ANIMATOR_DURATION_SCALE,0f)
        RuntimeEnvironment.getApplication().getSharedPreferences("connection",0).edit().clear().commit()
        controller=Robolectric.buildActivity(MainActivity::class.java).setup().visible();activity=controller.get()
    }
    @After fun stop() { controller.pause().stop().destroy() }
    private fun call(name:String) { MainActivity::class.java.getDeclaredMethod(name).apply { isAccessible=true }.invoke(activity) }
    private fun field(name:String)=MainActivity::class.java.getDeclaredField(name).apply { isAccessible=true }.get(activity)
    private fun texts(view:View=activity.window.decorView):List<String> {
        val own=if(view is TextView)listOf(view.text.toString()) else emptyList()
        return own+if(view is ViewGroup)(0 until view.childCount).flatMap { texts(view.getChildAt(it)) } else emptyList()
    }
    @Test fun connectionChooserHasTwoClearModesAndPublicFormReturnsToChooser() {
        call("computersPage");assertTrue(texts().containsAll(listOf("局域网扫描","公网连接")))
        MainActivity::class.java.getDeclaredMethod("publicConnectionPage",ComputerProfile::class.java).apply { isAccessible=true }.invoke(activity,null)
        assertEquals("public-connect",field("mode"));assertTrue(texts().contains("配对并连接"))
        activity.onBackPressed();assertEquals("computers",field("mode"))
    }
    @Test fun leavingForegroundReleasesDiscoveryAndNeverCreatesAComputer() {
        MainActivity::class.java.getDeclaredMethod("lanScanPage",String::class.java).apply { isAccessible=true }.invoke(activity,null)
        assertEquals("lan-scan",field("mode"));assertNotNull(field("lanDiscovery"))
        controller.pause();assertNull(field("lanDiscovery"))
        assertTrue(ComputerProfiles(activity.getSharedPreferences("connection",0)).all().isEmpty())
        controller.resume()
    }
}
