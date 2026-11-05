package org.watchchat.app

import android.net.Uri
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.shadows.ShadowBinder

@RunWith(RobolectricTestRunner::class)
@Config(sdk=[30])
class PairingProviderTest {
    @Test fun onlyAdbCanWriteAndPairingCanNeverBeReadThroughProvider() {
        val provider=Robolectric.buildContentProvider(PairingProvider::class.java).create().get()
        val uri=Uri.parse("content://org.watchchat.app.pairing/pairing")
        ShadowBinder.setCallingUid(12345)
        assertThrows(SecurityException::class.java) { provider.openFile(uri,"w") }
        ShadowBinder.setCallingUid(2000)
        assertThrows(IllegalArgumentException::class.java) { provider.openFile(uri,"r") }
        assertThrows(IllegalArgumentException::class.java) { provider.openFile(Uri.parse("content://org.watchchat.app.pairing/other"),"w") }
        provider.openFile(uri,"w").close()
        ShadowBinder.reset()
    }
}
