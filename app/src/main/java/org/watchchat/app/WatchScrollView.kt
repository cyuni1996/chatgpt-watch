package org.watchchat.app

import android.content.Context
import android.graphics.Canvas
import android.graphics.Paint
import android.os.SystemClock
import android.os.VibrationEffect
import android.os.Vibrator
import android.provider.Settings
import android.view.MotionEvent
import android.view.View
import android.view.ViewGroup
import android.widget.ScrollView
import kotlin.math.abs

/** Free scrolling with transient feedback. No snap, stretch, background timer or semantic selection. */
class WatchScrollView(context:Context):ScrollView(context) {
    var feedback:ScrollFeedback?=null
    var reading=false
    var interacting=false;private set
    private var downY=0f
    private var lastY=0
    private var focus:View?=null
    private var lastTick=-90L
    private var lastBoundary=-450L
    private var crownUntil=0L
    private val density=resources.displayMetrics.density
    private val idle=Runnable { interacting=false;feedback?.invalidate() }
    private fun haptic(boundary:Boolean) {
        val now=SystemClock.uptimeMillis()
        if(boundary) { if(now-lastBoundary<450)return;lastBoundary=now;lastTick=now }
        else { if(now-lastTick<90)return;lastTick=now }
        val prefs=context.getSharedPreferences("connection",0)
        if(!isHapticFeedbackEnabled || !prefs.getBoolean("ui.haptics",true) || Settings.System.getInt(context.contentResolver,Settings.System.HAPTIC_FEEDBACK_ENABLED,1)==0)return
        val vibrator=context.getSystemService(Vibrator::class.java)
        if(vibrator?.hasVibrator()==true)vibrator.vibrate(VibrationEffect.createOneShot(if(boundary)20 else 8,if(vibrator.hasAmplitudeControl()) { if(boundary)96 else 42 } else VibrationEffect.DEFAULT_AMPLITUDE))
    }
    fun range()=(getChildAt(0)?.height ?: 0).let { (it+paddingTop+paddingBottom-height).coerceAtLeast(0) }
    fun boundary(top:Boolean) { if(range()>0) { haptic(true);feedback?.boundary(top) } }
    fun rotary(axis:Float) {
        if(!axis.isFinite())return
        val delta=(-axis*19.2f*density).toInt().coerceIn((-54*density).toInt(),(54*density).toInt())
        if(delta==0)return
        if((delta<0 && !canScrollVertically(-1)) || (delta>0 && !canScrollVertically(1))) { boundary(delta<0);return }
        crownUntil=SystemClock.uptimeMillis()+500;interacting=true
        smoothScrollBy(0,delta);markMoving()
    }
    private fun markMoving() { removeCallbacks(idle);postDelayed(idle,180);feedback?.moved(this) }
    override fun onInterceptTouchEvent(event:MotionEvent):Boolean {
        if(event.actionMasked==MotionEvent.ACTION_DOWN)downY=event.y
        return super.onInterceptTouchEvent(event)
    }
    override fun onTouchEvent(event:MotionEvent):Boolean {
        when(event.actionMasked) {
            MotionEvent.ACTION_DOWN->{ downY=event.y;interacting=true }
            MotionEvent.ACTION_MOVE->{ val dy=event.y-downY;if(abs(dy)>8*density && ((dy>0 && !canScrollVertically(-1)) || (dy<0 && !canScrollVertically(1))))boundary(dy>0) }
            MotionEvent.ACTION_UP,MotionEvent.ACTION_CANCEL->markMoving()
        }
        return super.onTouchEvent(event)
    }
    override fun fling(velocityY:Int) { super.fling(velocityY.coerceIn((-240*density).toInt(),(240*density).toInt())) }
    override fun onScrollChanged(l:Int,t:Int,oldl:Int,oldt:Int) {
        super.onScrollChanged(l,t,oldl,oldt)
        if(interacting || SystemClock.uptimeMillis()<crownUntil)markMoving()
        if(reading) {
            if(SystemClock.uptimeMillis()<crownUntil && abs(t-lastY)>48*density) { haptic(false);lastY=t }
            return
        }
        val list=getChildAt(0) as? ViewGroup ?: return
        var nearest:View?=null;var best=Float.MAX_VALUE
        for(i in 0 until list.childCount) {
            val child=list.getChildAt(i)
            val distance=abs(child.top+child.height/2f-t-height/2f)
            if(child.isClickable && distance<best) { nearest=child;best=distance }
            val amount=(distance/(height/2f).coerceAtLeast(1f)).coerceIn(0f,1f)
            val scale=if(resources.configuration.fontScale>1.2f)1f else 1f-.08f*amount
            child.scaleX=scale;child.scaleY=scale;child.alpha=1f-.2f*amount
        }
        if(nearest!==focus) {
            if(interacting)haptic(false)
            focus?.foreground=null
            nearest?.foreground=android.graphics.drawable.GradientDrawable().apply { setColor(0x12D5BEF7);cornerRadius=14*density }
        }
        focus=nearest
    }
    fun stopFeedback() { removeCallbacks(idle);interacting=false;feedback?.stop() }
    override fun onDetachedFromWindow() { stopFeedback();super.onDetachedFromWindow() }
}

class ScrollFeedback(context:Context):View(context) {
    private val paint=Paint(Paint.ANTI_ALIAS_FLAG).apply { color=DragonTheme.ACCENT;strokeWidth=2*resources.displayMetrics.density;style=Paint.Style.STROKE;strokeCap=Paint.Cap.ROUND }
    private var source:WatchScrollView?=null
    private var movingAt=-1000L
    private var boundaryAt=-1000L
    private var top=true
    fun moved(view:WatchScrollView) { source=view;movingAt=SystemClock.uptimeMillis();invalidate() }
    fun boundary(atTop:Boolean) { val now=SystemClock.uptimeMillis();if(now-boundaryAt<450)return;top=atTop;boundaryAt=now;invalidate() }
    fun stop() { source=null;movingAt=-1000;boundaryAt=-1000;invalidate() }
    override fun onDraw(canvas:Canvas) {
        val now=SystemClock.uptimeMillis();val inset=5*resources.displayMetrics.density
        val view=source;val age=now-movingAt
        if(view!=null && view.range()>0 && age<1000) {
            val a=if(age<800)1f else (1000-age)/200f
            val fraction=(view.height.toFloat()/(view.range()+view.height)).coerceIn(.12f,.7f)
            val position=(view.scrollY.toFloat()/view.range()).coerceIn(0f,1f)
            paint.alpha=(120*a).toInt();canvas.drawArc(inset,inset,width-inset,height-inset,-35f+70f*(1-fraction)*position,70f*fraction,false,paint)
        }
        val boundaryAge=now-boundaryAt
        if(boundaryAge<360) { paint.alpha=(230*(1-boundaryAge/360f)).toInt();canvas.drawArc(inset,inset,width-inset,height-inset,if(top)250f else 70f,40f,false,paint) }
        if(age<1000 || boundaryAge<360)postInvalidateOnAnimation()
    }
}
