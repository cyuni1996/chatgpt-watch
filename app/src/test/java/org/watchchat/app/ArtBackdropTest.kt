package org.watchchat.app

import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

@RunWith(RobolectricTestRunner::class)
@Config(sdk=[30])
@GraphicsMode(GraphicsMode.Mode.NATIVE)
class ArtBackdropTest {
    @Test fun portraitAndPanelCoverAllEdgesForSquareAndRectangularBounds() {
        val source=Bitmap.createBitmap(100,100,Bitmap.Config.ARGB_8888).apply { eraseColor(Color.RED) }
        for(panel in listOf(false,true))for((width,height) in listOf(480 to 480,320 to 380)) {
            val output=Bitmap.createBitmap(width,height,Bitmap.Config.ARGB_8888)
            ArtBackdrop(source,panel,false).apply { setBounds(0,0,width,height);draw(Canvas(output)) }
            for((x,y) in listOf(0 to height/2,width-1 to height/2,width/2 to 0,width/2 to height-1,0 to 0,width-1 to height-1)) {
                val color=output.getPixel(x,y)
                assertEquals(255,Color.alpha(color))
                assertTrue("Art must reach $x,$y",Color.red(color)>Color.blue(color)+8)
            }
        }
    }
}
