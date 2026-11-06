package org.watchchat.app

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk=[30])
class ReleaseUpdatesTest {
    @Test fun comparesNumericVersionParts() {
        assertEquals("0.13.10",ReleaseUpdates.newerVersion(release("v0.13.10"),"0.13.9"))
        assertEquals("1.0.0",ReleaseUpdates.newerVersion(release("v1.0.0"),"0.13.9"))
        assertNull(ReleaseUpdates.newerVersion(release("v0.13.9"),"0.13.9"))
        assertNull(ReleaseUpdates.newerVersion(release("v0.13.0"),"0.13.9"))
    }

    @Test fun ignoresDraftsPreReleasesAndUnrecognizedVersions() {
        assertNull(ReleaseUpdates.newerVersion(release("v1.0.0").put("draft",true),"0.13.9"))
        assertNull(ReleaseUpdates.newerVersion(release("v1.0.0").put("prerelease",true),"0.13.9"))
        assertNull(ReleaseUpdates.newerVersion(release("v1.0.0-beta"),"0.13.9"))
        assertNull(ReleaseUpdates.newerVersion(release("v99999999999.0.0"),"0.13.9"))
        assertNull(ReleaseUpdates.newerVersion(JSONObject(),"0.13.9"))
        assertNull(ReleaseUpdates.newerVersion(release("v1.0.0"),"development"))
    }

    private fun release(tag: String) = JSONObject().put("tag_name",tag)
}
