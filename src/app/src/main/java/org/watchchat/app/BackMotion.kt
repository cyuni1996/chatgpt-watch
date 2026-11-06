package org.watchchat.app

import android.animation.ValueAnimator
import android.provider.Settings
import android.view.View
import android.view.animation.DecelerateInterpolator

/** One navigation transaction shared by touch, header Back and dialog Back. */
class BackMotion(private val target:()->View,private val preview:()->Unit,private val cleanup:()->Unit,private val commit:()->Unit,private val settled:()->Unit) {
    var busy=false;private set
    var settling=false;private set
    private var active:View?=null
    fun enabled(view:View)=ValueAnimator.areAnimatorsEnabled() && Settings.Global.getFloat(view.context.contentResolver,Settings.Global.ANIMATOR_DURATION_SCALE,1f)>0f
    fun drag(distance:Float) {
        if(settling)return
        if(!busy) { busy=true;active=target();active?.let { it.animate().withEndAction(null).cancel();it.alpha=1f };preview() }
        active?.let { it.translationX=distance.coerceIn(-it.width.toFloat(),it.width.toFloat()) }
    }
    fun finish(goBack:Boolean) {
        if(settling)return
        if(!busy)drag(0f)
        val view=active ?: return
        settling=true
        fun end() {
            if(!settling || active!==view)return
            view.animate().setListener(null);view.translationX=0f;active=null;busy=false;settling=false
            cleanup();if(goBack)commit();settled()
        }
        if(!enabled(view)) { end();return }
        val destination=if(goBack)(if(view.translationX<0)-1 else 1)*view.width.toFloat() else 0f
        view.animate().translationX(destination).setDuration(if(goBack)200 else 160).setInterpolator(DecelerateInterpolator())
            .withEndAction { end() }.start()
    }
    fun back() { if(!busy) { drag(0f);finish(true) } }
    fun cancel() {
        active?.let { it.animate().withEndAction(null).setListener(null).cancel();it.translationX=0f }
        active=null;busy=false;settling=false;cleanup()
    }
}
