package org.watchchat.app

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Canvas
import android.graphics.ColorFilter
import android.graphics.LinearGradient
import android.graphics.Paint
import android.graphics.Path
import android.graphics.PixelFormat
import android.graphics.RectF
import android.graphics.Shader
import android.graphics.drawable.Drawable

/** Static, screen-sized art shared by all panels; never decoded on each poll. */
object DragonTheme {
    const val INK = 0xFFF4F0FF.toInt()
    const val MUTED = 0xFFB5ABC8.toInt()
    const val ACCENT = 0xFFD5BEF7.toInt()
    const val SURFACE = 0xE62B253B.toInt()
    const val NIGHT = 0xFF100E1D.toInt()
    const val RUNNING = 0xFF9BE7CB.toInt()
    const val WAITING = 0xFFFFCC88.toInt()
    const val UNREAD = 0xFF9EC8FF.toInt()
    private val bitmaps = mutableMapOf<Int, Bitmap>()
    fun bitmap(context: Context, id: Int): Bitmap = bitmaps.getOrPut(id) {
        BitmapFactory.decodeResource(context.resources, id, BitmapFactory.Options().apply { inScaled = false })
    }
    fun backdrop(context: Context, panel: Boolean = false): Drawable {
        val prefs=context.getSharedPreferences("connection",Context.MODE_PRIVATE)
        return ArtBackdrop(if(prefs.getBoolean("ui.quietBackground",false))null else
            bitmap(context,if(panel)R.drawable.dragon_drawer else R.drawable.dragon_chat),panel,prefs.getBoolean("ui.deepBackground",false))
    }
}

internal class ArtBackdrop(private val image: Bitmap?, private val panel: Boolean, private val deeper: Boolean) : Drawable() {
    private val paint = Paint(Paint.ANTI_ALIAS_FLAG or Paint.FILTER_BITMAP_FLAG)
    private val area = RectF()
    private val destination = RectF()
    private var shade:Shader?=null
    override fun onBoundsChange(bounds:android.graphics.Rect) {
        area.set(bounds)
        image?.let {
            // The source portrait has a circular vignette. Overscan its edge as well as filling the rect.
            val scale=maxOf(area.width()/it.width,area.height()/it.height)*1.035f
            val w=it.width*scale;val h=it.height*scale
            destination.set(area.centerX()-w/2,area.centerY()-h/2,area.centerX()+w/2,area.centerY()+h/2)
        }
        shade=LinearGradient(0f,area.top,0f,area.bottom,
            intArrayOf(0xCE100E1D.toInt(),if(deeper)0xD0100E1D.toInt() else if(panel)0xB4100E1D.toInt() else 0x58100E1D,0xC8100E1D.toInt()),
            floatArrayOf(0f,.48f,1f),Shader.TileMode.CLAMP)
    }
    override fun draw(canvas: Canvas) {
        canvas.save();canvas.clipRect(bounds)
        canvas.drawColor(DragonTheme.NIGHT)
        paint.shader = null; paint.alpha = 255
        image?.let { canvas.drawBitmap(it,null,destination,paint) }
        paint.shader=shade
        canvas.drawRect(area, paint); paint.shader = null
        canvas.restore()
    }
    override fun setAlpha(alpha: Int) {}
    override fun setColorFilter(colorFilter: ColorFilter?) {}
    @Deprecated("Deprecated in Android") override fun getOpacity() = PixelFormat.OPAQUE
}
