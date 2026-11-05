package org.watchchat.app

import android.Manifest
import android.app.Activity
import android.app.Dialog
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.pm.PackageManager
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.media.AudioAttributes
import android.media.MediaPlayer
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.text.Editable
import android.text.TextWatcher
import android.text.TextUtils
import android.view.Gravity
import android.view.GestureDetector
import android.view.InputDevice
import android.view.KeyEvent
import android.view.MotionEvent
import android.view.View
import android.view.ViewGroup
import android.view.accessibility.AccessibilityManager
import android.graphics.Rect
import android.view.WindowInsets
import android.view.WindowManager
import android.view.inputmethod.EditorInfo
import android.view.inputmethod.InputMethodManager
import android.widget.EditText
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.net.URLEncoder
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.UUID
import java.util.concurrent.Executors

class MainActivity : Activity() {
    private var pool = Executors.newFixedThreadPool(3)
    @Volatile private var foregroundGeneration = 0
    private val jobGeneration = ThreadLocal<Int>()
    private val jobClient = ThreadLocal<BridgeClient>()
    private var pollFailures = 0
    private val ui = Handler(Looper.getMainLooper())
    private val prefs by lazy { getSharedPreferences("connection", MODE_PRIVATE) }
    private val computers by lazy { ComputerProfiles(prefs) }
    private var lanDiscovery:LanDiscovery?=null
    private var pairingClient:BridgeClient?=null
    private var connectionEpoch=0
    private var pausedPairTarget:ConnectionCandidate?=null
    private val ink = DragonTheme.INK
    private val muted = DragonTheme.MUTED
    private val accent = DragonTheme.ACCENT
    private val surface = DragonTheme.SURFACE
    private val backdrop = DragonTheme.NIGHT
    private val watchLayout by lazy { resources.displayMetrics.let { WatchLayout(it.widthPixels,it.heightPixels,it.density,resources.configuration.isScreenRound) } }
    private var client: BridgeClient? = null
    private var state = JSONObject()
    private var sessionId = ""
    @Volatile private var resumed = false
    private var fetching = false
    private var sending = false
    private var controlling = false
    private lateinit var headerTitles: LinearLayout
    private var approvalDialog: Dialog? = null
    private var approvalPopupQueued=false
    private val shownApprovals=mutableSetOf<String>()
    private var openApprovalToken = ""
    private var approvalStateLabel: TextView? = null
    private val approvalActions = mutableListOf<TextView>()
    private var editingDraft = false
    private var lastChat = ""
    private var lastSession = ""
    private var localError = ""
    private var recording: VoiceRecorder? = null
    private var voiceBusy = false
    private var player: MediaPlayer? = null
    private var playbackFile: File? = null
    private var playbackGeneration = 0
    private var lastSpoken = ""
    private var mode = "chat"
    private lateinit var root: FrameLayout
    private lateinit var chatPage:View
    private var previewPage:View?=null
    private val backMotion by lazy { BackMotion({ overlay ?: chatPage },{
        val previous=panelHistory.peekLast()?.view
        if(previous!=null && previous.parent==null) {
            root.addView(previous,if(overlay?.parent===root)root.indexOfChild(overlay) else root.childCount);previewPage=previous
        }
    },{ previewPage?.let { (it.parent as? ViewGroup)?.removeView(it) };previewPage=null },{
        hideKeyboard();if(overlay!=null)popPanel() else finishAndRemoveTask()
    },{ if(resumed)maybeShowApproval() }) }
    private data class DetailTarget(val id:String,val data:JSONObject)
    private var detailTarget:DetailTarget?=null
    private var modelsSaving=false
    private var managing=false
    private var modelRequest=0
    private lateinit var titleText: TextView
    private lateinit var statusText: TextView
    private lateinit var clock: TextView
    private lateinit var chatScroll: ScrollView
    private lateinit var chat: LinearLayout
    private lateinit var input: EditText
    private lateinit var mic: GlyphButton
    private lateinit var send: GlyphButton
    private lateinit var modelText: TextView
    private lateinit var projectText: TextView
    private var projectPickerCreatesChat = true
    private lateinit var banner: TextView
    private lateinit var latest: TextView
    private var overlay: View? = null
    private var activeScroll: ScrollView? = null
    private var gestureEligible=false
    private var gestureHandled=false
    private var protectedControl=false
    private var doubleTapTriggered=false
    private var shortcutLongPressed=false
    private var swipeStartX=0f
    private var swipeStartY=0f
    private var swipeEligible=false
    private var swipeClaimed=false
    private var usageSwipeEligible=false
    private var usageSwipeClaimed=false
    private data class PanelSnapshot(
        val view: View, val name: String, val scroll: ScrollView?,
        val drawerScroll: ScrollView?, val drawerRows: LinearLayout?, val search: EditText?,
        val approvalToken: String, val approvalLabel: TextView?, val approvalButtons: List<TextView>,val detail:DetailTarget?
    )
    private val panelHistory = java.util.ArrayDeque<PanelSnapshot>()
    private val touchGestures by lazy {
        GestureDetector(this,object:GestureDetector.SimpleOnGestureListener() {
            override fun onDown(event:MotionEvent)=true
            override fun onDoubleTap(event:MotionEvent):Boolean {
                if(!gestureEligible || mode!="chat" || recording!=null)return false
                doubleTapTriggered=true
                chatScroll.fullScroll(View.FOCUS_DOWN); latest.visibility=View.GONE
                return true
            }
        }).apply { setIsLongpressEnabled(false) }
    }
    private var drawerScroll: ScrollView? = null
    private var drawerRows: LinearLayout? = null
    private var search: EditText? = null
    private var drawerItems = JSONArray()
    private var drawerTab = "all"
    private var drawerQuery = ""
    private var drawerSearchExpanded = false
    private var drawerCursor: String? = null
    private var drawerRequest = 0
    private var drawerLoading = false
    private var drawerProjects = JSONArray()
    private val expandedProjects = mutableSetOf<String>()
    private val drawerStatusLabels = mutableMapOf<String,TextView>()
    private val drawerStatusLater = Runnable { refreshDrawerStatuses() }
    private var models = JSONArray()
    private var selectedModel = ""
    private var selectedEffort = ""
    private val bodies = linkedMapOf<String, TextView>()
    private val poll = object : Runnable {
        override fun run() { if (resumed) fetch() }
    }
    private val searchLater = Runnable { if (mode == "drawer") loadDrawer(true) }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.setDecorFitsSystemWindows(false)
        computers.migrateLegacy()
        importPairing()
        sessionId=computers.getState("sessionId")
        setupClient()
        createLayout()
        restoreDraft()
        updateControls()
        window.decorView.post { window.insetsController?.hide(WindowInsets.Type.statusBars()) }
        if (client == null) ui.post { computersPage() }
    }

    private fun importPairing() {
        val file=File(filesDir,"pairing.json")
        if(!file.exists())return
        runCatching {
            val data=JSONObject(file.readText())
            val url=data.getString("url"); val token=data.getString("token"); val pin=data.getString("certificateSha256")
            BridgeClient(url,token,pin)
            val id=data.optString("computerId").ifBlank { UUID.nameUUIDFromBytes(pin.toByteArray(Charsets.UTF_8)).toString() }
            val name=data.optString("computerName").ifBlank { "电脑 ${computers.all().size+1}" }
            computers.save(ComputerProfile(id,name,url,token,pin))
            file.delete()
        }.onFailure { localError="配对信息无效，请重新连接电脑" }
    }
    private fun setupClient() {
        client=runCatching { computers.active()?.let { BridgeClient(it.url,it.token,it.pin,mode=it.mode) } }.getOrNull()
    }
    private fun connectComputer(profile: ComputerProfile) {
        val next=BridgeClient(profile.url,profile.token,profile.pin,mode=profile.mode)
        saveDraft()
        computers.save(profile)
        foregroundGeneration++; ui.removeCallbacksAndMessages(null); approvalPopupQueued=false; shownApprovals.clear()
        client?.setForeground(false); pool.shutdownNow()
        recording?.stop(); recording=null; releasePlayback()
        fetching=false; sending=false; controlling=false; voiceBusy=false; pollFailures=0
        client=next; client?.setForeground(resumed)
        if(resumed)pool=Executors.newFixedThreadPool(3)
        sessionId=computers.getState("sessionId"); state=JSONObject(); localError=""
        lastChat=""; lastSession=""; lastSpoken=""; models=JSONArray()
        selectedModel=""; selectedEffort=""; drawerItems=JSONArray(); drawerCursor=null
        drawerQuery=""; drawerSearchExpanded=false; drawerTab="all"; drawerLoading=false; drawerProjects=JSONArray(); expandedProjects.clear(); drawerStatusLabels.clear()
        restoreDraft(); closeOverlay(); updateMessages(true); updateControls(); fetch()
    }
    override fun onResume() {
        super.onResume()
        foregroundGeneration++; resumed=true; pollFailures=0; approvalPopupQueued=false; shownApprovals.clear()
        if(pool.isShutdown)pool=Executors.newFixedThreadPool(3)
        client?.setForeground(true)
        updateControls()
        ui.removeCallbacks(poll); ui.post(poll)
        if(mode=="drawer")loadDrawer(true)
        else if(mode=="lan-scan")lanScanPage()
        else if(mode=="pair-device")pausedPairTarget?.let { pairingPaused(it) }
        else if(mode=="projects")projectPicker(projectPickerCreatesChat)
        else if(mode=="usage")usagePage()
        else if(mode=="models") { if(models.length()==0)openModels() else drawModels() }
    }
    override fun onPause() {
        backMotion.cancel();stopScrollFeedback(root)
        panelHistory.forEach { stopScrollFeedback(it.view) }
        overlay?.let { it.animate().cancel();it.alpha=1f;it.translationX=0f }
        stopConnectionTasks()
        resumed=false; foregroundGeneration++; approvalPopupQueued=false
        ui.removeCallbacksAndMessages(null); saveDraft(); drawerRequest++
        client?.setForeground(false); pool.shutdownNow()
        fetching=false; sending=false; controlling=false; voiceBusy=false
        managing=false;modelsSaving=false
        recording?.stop(); recording=null
        releasePlayback()
        window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        super.onPause()
    }
    override fun onDestroy() {
        backMotion.cancel()
        stopConnectionTasks()
        ui.removeCallbacksAndMessages(null); client?.setForeground(false); pool.shutdownNow()
        releasePlayback()
        approvalDialog?.dismiss(); approvalDialog=null
        panelHistory.clear()
        super.onDestroy()
    }
    private fun schedulePoll() {
        ui.removeCallbacks(poll)
        if(resumed)ui.postDelayed(poll,PollPolicy.delayMillis(
            sending || controlling || state.optBoolean("busy") || state.optBoolean("waitingOnApproval"),
            overlay!=null,pollFailures
        ))
    }
    private fun releasePlayback() {
        playbackGeneration++; player?.release(); player=null
        playbackFile?.delete(); playbackFile=null
    }
    private fun dp(n: Int) = (n*resources.displayMetrics.density).toInt()
    private fun currentThreadId() = if(state.isNull("threadId"))"" else state.optString("threadId")
    private fun shape(color: Int, radius: Int = 16) = GradientDrawable().apply {
        setColor(color); cornerRadius=dp(radius).toFloat()
    }
    private fun pressable(color:Int,radius:Int=18)=android.graphics.drawable.RippleDrawable(
        android.content.res.ColorStateList.valueOf(0x44D5BEF7),shape(color,radius),shape(Color.WHITE,radius))
    private fun TextView.mark(glyph:String, color:Int=accent, size:Int=14) {
        setCompoundDrawables(GlyphDrawable(glyph,color).apply { setBounds(0,0,dp(size),dp(size)) },null,null,null)
        compoundDrawablePadding=dp(6)
    }
    private fun text(value: String, size: Float = 13f, color: Int = ink, bold: Boolean = false) = TextView(this).apply {
        this.text=value; textSize=size; setTextColor(color); includeFontPadding=false
        if (bold) setTypeface(typeface, Typeface.BOLD)
    }
    private fun column() = LinearLayout(this).apply { orientation=LinearLayout.VERTICAL }
    private fun row() = LinearLayout(this).apply { orientation=LinearLayout.HORIZONTAL; gravity=Gravity.CENTER_VERTICAL }
    private fun icon(glyph: String, name: String, action: () -> Unit) = GlyphButton(this,glyph,ink).apply { contentDescription=name; setOnClickListener { action() } }
    private fun action(label: String, primary: Boolean = false, run: () -> Unit) = text(label,12f,if(primary)backdrop else ink).apply {
        gravity=Gravity.CENTER_VERTICAL or if(primary)Gravity.CENTER_HORIZONTAL else Gravity.START
        minHeight=dp(36); setPadding(dp(14),dp(8),dp(12),dp(8))
        background=pressable(if(primary)accent else surface,14); isClickable=true; isFocusable=true
        DragonGlyphs.forLabel(label)?.let { mark(it,if(primary)backdrop else accent) }
        layoutParams=LinearLayout.LayoutParams(-1,-2).apply { topMargin=dp(6) }
        setOnClickListener { run() }
    }
    private fun navigation(label:String,run:()->Unit)=action(label,run=run).apply {
        setCompoundDrawables(compoundDrawables[0],null,GlyphDrawable("forward",muted).apply { setBounds(0,0,dp(12),dp(12)) },null)
    }
    private fun stopScrollFeedback(view:View) {
        if(view is WatchScrollView)view.stopFeedback()
        if(view is ViewGroup)for(i in 0 until view.childCount)stopScrollFeedback(view.getChildAt(i))
    }
    private fun scrollView() = WatchScrollView(this).apply {
        activeScroll=this
        val host=(overlay as? FrameLayout) ?: root
        feedback=(host.findViewWithTag<View>("scroll-feedback") as? ScrollFeedback) ?: ScrollFeedback(this@MainActivity).also { it.tag="scroll-feedback";host.addView(it,FrameLayout.LayoutParams(-1,-1)) }
        isFillViewport=true; isVerticalScrollBarEnabled=false; overScrollMode=View.OVER_SCROLL_NEVER
        setPadding(0,0,0,dp(24));clipToPadding=false
        // Android fades transparent content toward black, leaving a stripe over the artwork.
        isVerticalFadingEdgeEnabled=false;isHorizontalFadingEdgeEnabled=false;setFadingEdgeLength(0)
        isFocusableInTouchMode=true
        setOnGenericMotionListener { _, event ->
            if (event.action == MotionEvent.ACTION_SCROLL) { rotary(event.getAxisValue(MotionEvent.AXIS_SCROLL)); true } else false
        }
    }
    override fun dispatchGenericMotionEvent(event:MotionEvent):Boolean {
        if(event.action==MotionEvent.ACTION_SCROLL && event.isFromSource(InputDevice.SOURCE_ROTARY_ENCODER)) {
            if(window.decorView.rootWindowInsets?.isVisible(WindowInsets.Type.ime())==true)return super.dispatchGenericMotionEvent(event)
            val target=if(overlay==null)chatScroll else activeScroll
            if(target!=null && target.isAttachedToWindow) {
                val amount=event.getAxisValue(MotionEvent.AXIS_SCROLL)
                if(target is WatchScrollView)target.rotary(amount)
                return true
            }
        }
        return super.dispatchGenericMotionEvent(event)
    }
    private fun onInteractiveControl(view:View,x:Int,y:Int,textOnly:Boolean=false):Boolean {
        val bounds=Rect()
        if(!view.getGlobalVisibleRect(bounds) || !bounds.contains(x,y))return false
        if(view is EditText || (!textOnly && (view is GlyphButton || (view is TextView && view.isClickable))))return true
        if(view is ViewGroup)for(i in view.childCount-1 downTo 0)if(onInteractiveControl(view.getChildAt(i),x,y,textOnly))return true
        return false
    }
    override fun dispatchTouchEvent(event:MotionEvent):Boolean {
        if(!::root.isInitialized || (getSystemService(Context.ACCESSIBILITY_SERVICE) as AccessibilityManager).isTouchExplorationEnabled)return super.dispatchTouchEvent(event)
        if(backMotion.settling)return true
        if(event.actionMasked==MotionEvent.ACTION_DOWN) {
            gestureHandled=false
            swipeStartX=event.rawX; swipeStartY=event.rawY; swipeClaimed=false; usageSwipeClaimed=false
            usageSwipeEligible=overlay==null && recording==null && event.y in dp(12).toFloat()..(watchLayout.chatTop+watchLayout.chatButton).toFloat()
            val protected=onInteractiveControl(input,event.rawX.toInt(),event.rawY.toInt()) || onInteractiveControl(mic,event.rawX.toInt(),event.rawY.toInt()) || onInteractiveControl(send,event.rawX.toInt(),event.rawY.toInt()) || onInteractiveControl(modelText,event.rawX.toInt(),event.rawY.toInt())
            protectedControl=protected
            swipeEligible=recording==null && !protected && !onInteractiveControl(root,event.rawX.toInt(),event.rawY.toInt(),textOnly=true)
            gestureEligible=recording==null && !onInteractiveControl(root,event.rawX.toInt(),event.rawY.toInt(),textOnly=overlay!=null) && (overlay!=null || event.y in chatScroll.top.toFloat()..chatScroll.bottom.toFloat())
        }
        if(event.pointerCount>1) { gestureEligible=false; swipeEligible=false; usageSwipeEligible=false }
        val dx=event.rawX-swipeStartX; val dy=event.rawY-swipeStartY
        if(event.actionMasked==MotionEvent.ACTION_MOVE && protectedControl && !gestureHandled && kotlin.math.hypot(dx,dy)>android.view.ViewConfiguration.get(this).scaledTouchSlop) {
            val cancel=MotionEvent.obtain(event).apply { action=MotionEvent.ACTION_CANCEL };super.dispatchTouchEvent(cancel);cancel.recycle();gestureHandled=true
        }
        if(event.actionMasked==MotionEvent.ACTION_MOVE && usageSwipeEligible && !usageSwipeClaimed) {
            if(dy < -dp(18) || (kotlin.math.abs(dx)>dp(18) && kotlin.math.abs(dx)>=kotlin.math.abs(dy)))usageSwipeEligible=false
            else if(dy>dp(18) && dy>kotlin.math.abs(dx)*1.5f) {
                usageSwipeClaimed=true; gestureEligible=false; swipeEligible=false
                val cancel=MotionEvent.obtain(event).apply { action=MotionEvent.ACTION_CANCEL }
                super.dispatchTouchEvent(cancel); touchGestures.onTouchEvent(cancel); cancel.recycle()
            }
        }
        if(usageSwipeClaimed) {
            if(event.actionMasked==MotionEvent.ACTION_UP || event.actionMasked==MotionEvent.ACTION_CANCEL) {
                val open=event.actionMasked==MotionEvent.ACTION_UP && usageSwipeEligible && dy>=dp(64) && dy>kotlin.math.abs(dx)*1.5f
                usageSwipeClaimed=false; usageSwipeEligible=false
                if(open)usagePage()
            }
            return true
        }
        if(event.actionMasked==MotionEvent.ACTION_MOVE && swipeEligible && !swipeClaimed) {
            if(kotlin.math.abs(dy)>dp(18) && kotlin.math.abs(dy)>=kotlin.math.abs(dx))swipeEligible=false
            else if(kotlin.math.abs(dx)>dp(18) && kotlin.math.abs(dx)>kotlin.math.abs(dy)*1.5f) {
                swipeClaimed=true; gestureEligible=false
                val cancel=MotionEvent.obtain(event).apply { action=MotionEvent.ACTION_CANCEL }
                super.dispatchTouchEvent(cancel); touchGestures.onTouchEvent(cancel); cancel.recycle()
            }
        }
        if(swipeClaimed) {
            if(event.actionMasked==MotionEvent.ACTION_MOVE)backMotion.drag(dx)
            if(event.actionMasked==MotionEvent.ACTION_UP || event.actionMasked==MotionEvent.ACTION_CANCEL) {
                val goBack=event.actionMasked==MotionEvent.ACTION_UP && swipeEligible && kotlin.math.abs(dx)>=dp(64) && kotlin.math.abs(dx)>kotlin.math.abs(dy)*1.5f
                swipeClaimed=false; swipeEligible=false
                backMotion.finish(goBack)
            }
            return true
        }
        if(gestureHandled) { if(event.actionMasked==MotionEvent.ACTION_UP || event.actionMasked==MotionEvent.ACTION_CANCEL)gestureHandled=false;return true }
        doubleTapTriggered=false
        if(gestureEligible)touchGestures.onTouchEvent(event)
        else if(event.actionMasked==MotionEvent.ACTION_DOWN) {
            val cancel=MotionEvent.obtain(event).apply { action=MotionEvent.ACTION_CANCEL }
            touchGestures.onTouchEvent(cancel);cancel.recycle()
        }
        // Horizontal swipes share the same back stack as the back key and header.
        if(doubleTapTriggered && event.actionMasked==MotionEvent.ACTION_DOWN) {
            val cancel=MotionEvent.obtain(event).apply { action=MotionEvent.ACTION_CANCEL }
            super.dispatchTouchEvent(cancel);touchGestures.onTouchEvent(cancel);cancel.recycle();gestureHandled=true
            return true
        }
        return super.dispatchTouchEvent(event)
    }
    // Wear's primary stem is reserved by the OS. Only assignable app keys are handled.
    private fun appShortcutKey(code:Int)=code in listOf(KeyEvent.KEYCODE_STEM_1,KeyEvent.KEYCODE_STEM_2,KeyEvent.KEYCODE_STEM_3)
    override fun onKeyDown(keyCode:Int,event:KeyEvent):Boolean {
        if(appShortcutKey(keyCode)) { if(event.repeatCount==0) { shortcutLongPressed=false;event.startTracking() };return true }
        return super.onKeyDown(keyCode,event)
    }
    override fun onKeyLongPress(keyCode:Int,event:KeyEvent):Boolean {
        if(appShortcutKey(keyCode)) { shortcutLongPressed=true;hideKeyboard();if(overlay!=null)navigateBack() else { chatScroll.fullScroll(View.FOCUS_DOWN);latest.visibility=View.GONE };return true }
        return super.onKeyLongPress(keyCode,event)
    }
    override fun onKeyUp(keyCode:Int,event:KeyEvent):Boolean {
        if(appShortcutKey(keyCode)) { if(!event.isCanceled && !shortcutLongPressed) { if(overlay!=null)closeOverlay();if(mic.isEnabled)toggleRecording() };return true }
        return super.onKeyUp(keyCode,event)
    }
    private fun toast(message: String) { Toast.makeText(this,message,Toast.LENGTH_SHORT).show() }
    private fun requestClient(): BridgeClient {
        if(jobGeneration.get()!=foregroundGeneration || Thread.currentThread().isInterrupted)
            throw java.io.InterruptedIOException("应用已离开前台")
        return jobClient.get() ?: error("连接已结束")
    }
    private fun postResult(result: () -> Unit) {
        val generation=jobGeneration.get() ?: foregroundGeneration
        ui.post { if(resumed && generation==foregroundGeneration && !isFinishing && !isDestroyed)result() }
    }
    private fun work(job: () -> Unit) {
        if(!resumed || pool.isShutdown)return
        val generation=foregroundGeneration; val bridge=client
        pool.execute {
            jobGeneration.set(generation); jobClient.set(bridge)
            try { job() } catch (error: Exception) {
                postResult {
                    sending=false; controlling=false; voiceBusy=false
                    localError=error.message?.take(180) ?: "连接失败，请检查电脑"
                    if(mode=="drawer") { drawerLoading=false; drawDrawerRows() }
                    updateControls(); toast(localError)
                }
            } finally { jobGeneration.remove(); jobClient.remove() }
        }
    }
    private fun hideKeyboard() { (getSystemService(Context.INPUT_METHOD_SERVICE) as InputMethodManager).hideSoftInputFromWindow(input.windowToken,0); input.clearFocus() }
    private fun saveDraft() { if (::input.isInitialized) computers.putState("draft:$sessionId",input.text.toString()) }
    private fun restoreDraft() {
        editingDraft=true; input.setText(computers.getState("draft:$sessionId")); input.setSelection(input.text.length); editingDraft=false
    }

    private fun createLayout() {
        root=FrameLayout(this).apply { background=DragonTheme.backdrop(this@MainActivity); isFocusableInTouchMode=true }
        val metrics=watchLayout
        val main=column().apply { setPadding(0,metrics.chatTop,0,metrics.chatBottom) }
        val toolbar=row()
        toolbar.addView(icon("menu","打开历史对话") { openDrawer() },LinearLayout.LayoutParams(metrics.chatButton,metrics.chatButton))
        headerTitles=column().apply {
            gravity=Gravity.CENTER_VERTICAL
            setOnClickListener { conversationInfo() }
        }
        titleText=text("新对话",12f,ink,true).apply { maxLines=1; ellipsize=TextUtils.TruncateAt.END; gravity=Gravity.CENTER }
        statusText=text("连接中 ⌄",8f,muted).apply { maxLines=1; ellipsize=TextUtils.TruncateAt.END; gravity=Gravity.CENTER; setPadding(0,dp(2),0,0) }
        headerTitles.addView(titleText,LinearLayout.LayoutParams(-1,-2)); headerTitles.addView(statusText,LinearLayout.LayoutParams(-1,-2))
        toolbar.addView(headerTitles,LinearLayout.LayoutParams(0,-1,1f))
        toolbar.addView(icon("gear","设置") { settingsPage() },LinearLayout.LayoutParams(metrics.chatButton,metrics.chatButton))
        main.addView(toolbar,LinearLayout.LayoutParams(-1,metrics.chatButton).apply { leftMargin=metrics.chatHeaderInset; rightMargin=metrics.chatHeaderInset })
        chatScroll=scrollView().apply { reading=true;contentDescription="聊天消息"; isVerticalFadingEdgeEnabled=false; clipToPadding=true; setPadding(dp(20),0,dp(20),0) }
        chat=column().apply { setPadding(0,dp(2),0,dp(2)) }
        chatScroll.addView(chat,FrameLayout.LayoutParams(-1,-2))
        main.addView(chatScroll,LinearLayout.LayoutParams(-1,0,1f))
        banner=text("",9f,Color.rgb(242,173,146)).apply { gravity=Gravity.CENTER; maxLines=2; ellipsize=TextUtils.TruncateAt.END; visibility=View.GONE; setPadding(dp(38),0,dp(38),dp(2)) }
        main.addView(banner,LinearLayout.LayoutParams(-1,-2))
        val composer=column().apply { gravity=Gravity.CENTER_HORIZONTAL; setPadding(0,metrics.chatComposerGap,0,0) }
        val box=row().apply { background=shape(0xED282236.toInt(),21); setPadding(dp(6),0,dp(3),0) }
        input=EditText(this).apply {
            hint="发消息…"; textSize=13f; setTextColor(ink); setHintTextColor(muted); includeFontPadding=false
            background=null; setPadding(dp(5),dp(3),dp(2),dp(3)); minLines=1; maxLines=2; gravity=Gravity.CENTER_VERTICAL
            inputType=android.text.InputType.TYPE_CLASS_TEXT or android.text.InputType.TYPE_TEXT_FLAG_MULTI_LINE or android.text.InputType.TYPE_TEXT_FLAG_CAP_SENTENCES
            imeOptions=EditorInfo.IME_ACTION_SEND or EditorInfo.IME_FLAG_NO_EXTRACT_UI
            contentDescription="消息输入框"
            addTextChangedListener(object : TextWatcher {
                override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) {}
                override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) { if(!editingDraft)saveDraft(); if(::send.isInitialized)updateControls() }
                override fun afterTextChanged(s: Editable?) {}
            })
            setOnEditorActionListener { _, action, event -> if(action==EditorInfo.IME_ACTION_SEND || (event?.keyCode==KeyEvent.KEYCODE_ENTER && event.action==KeyEvent.ACTION_DOWN && !event.isShiftPressed)) { if(!replyInProgress())sendMessage(); true } else false }
        }
        box.addView(input,LinearLayout.LayoutParams(0,-1,1f))
        mic=icon("mic","语音输入") { toggleRecording() }.apply { tone=GlyphButton.Tone.QUIET }
        box.addView(mic,LinearLayout.LayoutParams(metrics.chatButton,metrics.chatInputHeight))
        send=icon("send","发送消息") { if(replyInProgress())interruptReply() else sendMessage() }.apply { tone=GlyphButton.Tone.ACCENT;tint=backdrop }
        box.addView(send,LinearLayout.LayoutParams(metrics.chatButton,metrics.chatInputHeight))
        composer.addView(box,LinearLayout.LayoutParams(metrics.chatComposerWidth,metrics.chatInputHeight))
        createContextControls()
        composer.addView(modelText,LinearLayout.LayoutParams(metrics.modelWidth,metrics.modelTouchHeight).apply { topMargin=metrics.chatComposerGap })
        main.addView(composer,LinearLayout.LayoutParams(-1,metrics.chatComposerHeight))
        chatPage=main
        root.addView(main,FrameLayout.LayoutParams(-1,-1))
        root.findViewWithTag<View>("scroll-feedback")?.bringToFront()
        clock=text("",8f,muted).apply { gravity=Gravity.CENTER }
        root.addView(clock,FrameLayout.LayoutParams(dp(60),dp(14),Gravity.TOP or Gravity.CENTER_HORIZONTAL).apply { topMargin=dp(8) })
        latest=action("↓ 最新消息") { chatScroll.fullScroll(View.FOCUS_DOWN); latest.visibility=View.GONE }.apply { textSize=9f; minHeight=0; visibility=View.GONE }
        root.addView(latest,FrameLayout.LayoutParams(dp(82),dp(26),Gravity.BOTTOM or Gravity.CENTER_HORIZONTAL).apply { bottomMargin=metrics.chatBottom+metrics.chatComposerHeight+dp(3) })
        chatScroll.setOnScrollChangeListener { _: View, _: Int, _: Int, _: Int, _: Int -> if(atBottom())latest.visibility=View.GONE }
        setContentView(root)
        root.requestFocus()
        main.addOnLayoutChangeListener { _,_,_,_,bottom,_,_,_,oldBottom -> if(bottom!=oldBottom && atBottom())chatScroll.post { chatScroll.fullScroll(View.FOCUS_DOWN) } }
    }

    private fun atBottom() = chat.height-chatScroll.scrollY-chatScroll.height < dp(8)
    private fun fetch() {
        val bridge=client ?: return
        if(!resumed || fetching)return
        ui.removeCallbacks(poll)
        val selected=sessionId; fetching=true
        work {
            try {
                val value=bridge.json("/api/state"+if(selected.isEmpty())"" else "?sessionId=$selected")
                postResult {
                    fetching=false; pollFailures=0
                    if(selected==sessionId) {
                        state=value; sessionId=value.getString("id")
                        if(selected!=sessionId)computers.putState("sessionId",sessionId)
                        if(localError.startsWith("电脑离线"))localError=""
                        updateMessages(); updateControls()
                    }
                    schedulePoll()
                }
            } catch(error: Exception) {
                postResult {
                    fetching=false; pollFailures=minOf(pollFailures+1,5)
                    if(selected==sessionId) { localError="电脑离线或连接失败"; updateControls() }
                    schedulePoll()
                }
            }
        }
    }

    private fun updateControls() {
        if(!::send.isInitialized)return
        val connected=client!=null && state.optBoolean("connected") && !localError.startsWith("电脑离线")
        val busy=state.optBoolean("busy")
        titleText.text=(if(state.isNull("title"))"新对话" else state.optString("title","新对话")).removePrefix("手表 · ").ifEmpty { "新对话" }
        clock.text=SimpleDateFormat("HH:mm",Locale.CHINA).format(Date())
        statusText.text=when { recording!=null -> "录音中"; voiceBusy -> "识别中"; !connected -> "未连接"; controlling -> "同步中"; state.optBoolean("waitingOnApproval") -> "待确认"; sending -> "发送中"; busy -> "回复中"; else -> "在线" }
        val approvals=state.optJSONArray("approvals") ?: JSONArray()
        headerTitles.isClickable=true
        headerTitles.contentDescription="查看对话详情"
        if(mode=="approval" && openApprovalToken.isNotEmpty()) {
            val pending=(0 until approvals.length()).any { approvals.getJSONObject(it).optString("token")==openApprovalToken }
            approvalStateLabel?.text=if(!pending)"已处理或已结束" else if(controlling)"正在提交，请稍候…" else "选择后会同步到电脑"
            approvalActions.forEach { it.isEnabled=pending && !controlling; it.alpha=if(it.isEnabled)1f else .4f }
        }
        statusText.setTextColor(if(connected)accent else muted)
        val error=localError.ifEmpty { state.optString("error") }
        banner.text=error; banner.visibility=if(error.isEmpty())View.GONE else View.VISIBLE
        mic.glyph=if(recording!=null)"stop" else "mic"; mic.tint=if(recording!=null)Color.rgb(255,126,126) else ink
        mic.contentDescription=if(recording!=null)"结束录音" else "语音输入"
        mic.isEnabled=connected && !voiceBusy && !sending; mic.invalidate()
        input.isEnabled=recording==null && !voiceBusy
        input.hint=if(recording!=null)"正在聆听…" else if(voiceBusy)"识别中…" else "发消息…"
        val stopping=replyInProgress()
        send.glyph=if(stopping)"stop" else "send"
        send.isEnabled=if(stopping)connected && state.optBoolean("canInterrupt") && !controlling && !sending
            else connected && input.text.toString().isNotBlank() && !sending && recording==null && !voiceBusy && !state.optBoolean("archived")
        send.contentDescription=if(stopping)"停止本次回复" else "发送消息"
        send.alpha=if(send.isEnabled)1f else .42f
        send.invalidate()
        val settings=state.optJSONObject("settings") ?: JSONObject()
        val modelName=settings.optString("model").ifBlank { "跟随电脑" }
        val thinking=settings.optString("thinking").let { if(it.isBlank())"默认" else effortName(it) }
        modelText.text=modelName.removePrefix("gpt-")+" · $thinking ⌄"
        modelText.contentDescription="模型与思考强度：$modelName · $thinking"
        modelText.isEnabled=connected;modelText.alpha=if(connected)1f else .5f
        val projectName=if(state.isNull("projectName"))"" else state.optString("projectName")
        projectText.text=if(projectName.isNotBlank())projectName+(if(currentThreadId().isBlank())" ⌄" else "") else if(currentThreadId().isBlank())"不选项目 ⌄" else "其他聊天"
        projectText.contentDescription="当前项目："+(projectName.ifBlank { "不选项目" })
        projectText.isEnabled=client!=null && !sending
        if(resumed && (recording!=null || voiceBusy))window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON) else window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        if(resumed && mode=="chat" && !busy && recording==null && prefs.getBoolean("autoRead",false)) {
            val messages=state.optJSONArray("messages") ?: JSONArray()
            val reply=(messages.length()-1 downTo 0).map { messages.getJSONObject(it) }.firstOrNull { it.optString("role")=="assistant" && it.optString("phase")!="commentary" }
            val id=reply?.optString("id") ?: ""
            if(id.isNotEmpty() && id!=lastSpoken) { lastSpoken=id; speak(id) }
        }
        maybeShowApproval()
    }

    private fun replyInProgress()=state.optBoolean("busy") || state.optBoolean("canInterrupt")
    private fun maybeShowApproval() {
        val items=state.optJSONArray("approvals") ?: return
        val tokens=(0 until items.length()).map { items.getJSONObject(it).optString("token") }.toSet()
        shownApprovals.retainAll(tokens)
        if(!resumed || overlay!=null || backMotion.busy || approvalPopupQueued || recording!=null || voiceBusy || sending || controlling)return
        val candidate=(0 until items.length()).map { items.getJSONObject(it) }.firstOrNull { it.optString("token").isNotEmpty() && it.optString("token") !in shownApprovals } ?: return
        val selected=sessionId; val token=candidate.getString("token")
        approvalPopupQueued=true
        postResult {
            approvalPopupQueued=false
            val pending=state.optJSONArray("approvals") ?: JSONArray()
            val item=(0 until pending.length()).map { pending.getJSONObject(it) }.firstOrNull { it.optString("token")==token }
            if(selected==sessionId && overlay==null && item!=null && recording==null && !voiceBusy) {
                shownApprovals.add(token); approvalPage(item)
            }
        }
    }

    private fun updateMessages(force: Boolean=false, older: Boolean=false) {
        val messages=state.optJSONArray("messages") ?: JSONArray()
        val signature=messages.toString()+state.optBoolean("hasOlder")
        val changedSession=lastSession!=sessionId
        if(!force && !changedSession && signature==lastChat)return
        val interacting=(chatScroll as WatchScrollView).interacting || backMotion.busy
        val follow=changedSession || (atBottom() && !interacting)
        val oldY=chatScroll.scrollY; val oldHeight=chat.height
        val ids=(0 until messages.length()).map { messages.getJSONObject(it).getString("id") }
        val existing=bodies.keys.toList()
        val appendOnly=!force && !changedSession && existing.size<=ids.size && existing==ids.take(existing.size) && existing.isNotEmpty()
        if(!appendOnly) {
            chat.removeAllViews(); bodies.clear()
            if(state.optBoolean("hasOlder"))chat.addView(action("加载更早的消息") { loadOlder() })
        }
        if(messages.length()==0) {
            chat.addView(text("有什么想聊的？",15f,ink,true).apply { setPadding(0,dp(25),0,dp(8)) },LinearLayout.LayoutParams(dp(110),-2))
            chat.addView(text("在下方输入，\n或点击麦克风。",11f,muted),LinearLayout.LayoutParams(dp(108),-2))
        }
        for(i in 0 until messages.length()) {
            val message=messages.getJSONObject(i); val id=message.getString("id")
            if(bodies[id]==null) {
                val user=message.getString("role")=="user"
                val card=column().apply {
                    setPadding(dp(10),dp(8),dp(10),dp(8))
                    background=shape(if(user)0xEB413354.toInt() else 0xD51B182A.toInt(),16)
                    layoutParams=LinearLayout.LayoutParams(-1,-2).apply { topMargin=dp(6); if(user)leftMargin=dp(26) }
                    setOnLongClickListener { messageMenu(id); true }
                }
                card.addView(text(if(user)"你" else "ChatGPT",8f,if(user)muted else accent).apply {
                    setPadding(0,0,0,dp(4))
                    if(!user)mark("settings",accent,10)
                })
                val body=text("",prefs.getInt("fontSize",13).toFloat()).apply {
                    setLineSpacing(dp(2).toFloat(),1f)
                    setOnLongClickListener { messageMenu(id); true }
                }
                card.addView(body,LinearLayout.LayoutParams(-1,-2)); bodies[id]=body; chat.addView(card)
            }
            val raw=message.optString("text")
            val body=bodies[id]!!
            if(body.tag!=raw) { body.text=ChatText.format(raw); body.tag=raw }
        }
        lastChat=signature; lastSession=sessionId
        chatScroll.post {
            when { changedSession || follow -> chatScroll.fullScroll(View.FOCUS_DOWN); older -> chatScroll.scrollTo(0,oldY+(chat.height-oldHeight)); else -> { chatScroll.scrollTo(0,oldY); if(!force)latest.visibility=View.VISIBLE } }
        }
        val lastAssistant=(messages.length()-1 downTo 0).map { messages.getJSONObject(it) }.firstOrNull { it.optString("role")=="assistant" }
        val voiceId=lastAssistant?.optString("id") ?: ""
        if(changedSession)lastSpoken=voiceId
    }

    private fun loadOlder() {
        val selected=sessionId
        work { val value=requestClient().json("/api/history/older",JSONObject().put("sessionId",selected)); postResult { if(selected==sessionId) { state=value; updateMessages(true,true) } } }
    }
    private fun setSession(value: JSONObject) {
        saveDraft(); recording?.stop(); recording=null; releasePlayback()
        sessionId=value.getString("id"); state=value; localError=""; lastSession=""; lastSpoken=""; shownApprovals.clear()
        computers.putState("sessionId",sessionId); restoreDraft(); closeOverlay(); updateMessages(true); updateControls(); fetch()
    }
    private fun newChat() {
        projectPicker(true)
    }
    private fun projectPicker(create: Boolean) {
        projectPickerCreatesChat=create
        val selected=sessionId
        val page=panel("projects"); pageHeader(page,"选择项目")
        val picker=overlay
        val scroll=scrollView(); val list=column()
        page.addView(scroll,LinearLayout.LayoutParams(-1,0,1f)); scroll.addView(list)
        list.addView(text("正在读取电脑项目…",11f,muted))
        work {
            val value=try { requestClient().json("/api/projects") } catch(error:Exception) {
                postResult {
                    if(overlay===picker) {
                        list.removeAllViews()
                        list.addView(text(error.message ?: "项目读取失败",11f,muted))
                        list.addView(action("重新读取项目") { projectPicker(create) })
                    }
                }
                return@work
            }
            postResult {
                if(overlay!==picker)return@postResult
                list.removeAllViews()
                list.addView(text("发送第一条消息后创建电脑会话",10f,muted).apply { gravity=Gravity.CENTER; setPadding(0,dp(6),0,dp(5)) })
                var choosing=false
                fun option(id:String?,name:String) {
                    val selectedProject=!create && (if(state.isNull("projectId"))null else state.optString("projectId"))==id
                    val button=action((if(selectedProject)"✓ " else "")+name) {
                        if(!choosing) {
                            choosing=true
                            work {
                                try {
                                    val body=JSONObject().put("projectId",id ?: JSONObject.NULL)
                                    if(!create)body.put("sessionId",selected)
                                    val result=requestClient().json(if(create)"/api/session/new" else "/api/session/project",body)
                                    postResult {
                                        choosing=false
                                        if(overlay===picker && selected==sessionId) {
                                            if(create)setSession(result.getJSONObject("state"))
                                            else { state=result; closeOverlay(); updateControls() }
                                        }
                                    }
                                } catch(error:Exception) { postResult { choosing=false; if(overlay===picker)toast(error.message ?: "选择失败，请重试") } }
                            }
                        }
                    }
                    button.apply {
                        gravity=Gravity.CENTER_VERTICAL or Gravity.START
                        minHeight=dp(42);setPadding(dp(12),dp(8),dp(12),dp(8))
                        mark(if(id==null)"quote" else "folder",accent,17)
                        isSelected=selectedProject
                        if(selectedProject)background=pressable(0xFF493B61.toInt())
                    }
                    list.addView(button)
                }
                val projects=value.getJSONArray("projects")
                for(i in 0 until projects.length()) { val item=projects.getJSONObject(i); option(item.getString("id"),item.getString("name")) }
                option(null,"不选项目")
                list.addView(action("刷新项目") { projectPicker(create) })
            }
        }
    }
    private fun linkChat(threadId: String) {
        hideKeyboard()
        work { val value=requestClient().json("/api/session/link",JSONObject().put("threadId",threadId)); postResult { setSession(value) } }
    }

    private fun sendMessage() {
        val bridge=client ?: return
        val value=input.text.toString().trim()
        if(value.isEmpty() || sending || recording!=null || voiceBusy || replyInProgress())return
        if(value.length>8000) { toast("消息太长，请分段发送"); return }
        val selected=sessionId
        val key=if(computers.getState("pendingText:$selected")==value)computers.getState("pendingId:$selected").ifEmpty { UUID.randomUUID().toString() } else UUID.randomUUID().toString()
        prefs.edit().putString(computers.stateKey("pendingText:$selected"),value).putString(computers.stateKey("pendingId:$selected"),key).apply()
        sending=true; localError=""; updateControls(); hideKeyboard()
        work {
            val result=bridge.json("/api/message",JSONObject().put("sessionId",selected).put("text",value).put("requestId",key).put("allowFollowup",true))
            postResult {
                prefs.edit().remove(computers.stateKey("pendingText:$selected")).remove(computers.stateKey("pendingId:$selected")).apply(); sending=false
                if(selected==sessionId) {
                    if(input.text.toString().trim()==value)input.setText("")
                    state=result; localError=""; updateMessages(); updateControls(); chatScroll.post { chatScroll.fullScroll(View.FOCUS_DOWN) }
                }
                schedulePoll()
            }
        }
    }

    private fun detachPanel() {
        if(backMotion.busy)backMotion.cancel()
        stopConnectionTasks()
        ui.removeCallbacks(searchLater); ui.removeCallbacks(drawerStatusLater); drawerRequest++
        approvalDialog?.dismiss(); approvalDialog=null
        overlay?.let { it.animate().cancel();it.alpha=1f;it.translationX=0f; (it.parent as? ViewGroup)?.removeView(it) }
        overlay=null; drawerRows=null; drawerScroll=null; search=null; mode="chat"
        openApprovalToken=""; approvalStateLabel=null; approvalActions.clear()
        activeScroll=if(::chatScroll.isInitialized)chatScroll else null
    }
    private fun closeOverlay() { detachPanel(); panelHistory.clear() }
    private fun popPanel() {
        detachPanel()
        val previous=panelHistory.pollLast() ?: return
        overlay=previous.view; mode=previous.name; activeScroll=previous.scroll
        drawerScroll=previous.drawerScroll; drawerRows=previous.drawerRows; search=previous.search
        openApprovalToken=previous.approvalToken; approvalStateLabel=previous.approvalLabel
        approvalActions.addAll(previous.approvalButtons)
        detailTarget=previous.detail
        root.addView(previous.view,FrameLayout.LayoutParams(-1,-1))
        if(mode=="approval")showApprovalDialog()
        if(mode=="drawer") { if(drawerLoading)loadDrawer(true) else { drawDrawerRows(); ui.post(drawerStatusLater) } }
        else if(mode=="lan-scan")lanScanPage()
        else if(mode=="pair-device")pausedPairTarget?.let { pairingPaused(it) }
        updateControls()
    }
    private fun navigateBack() {
        hideKeyboard();backMotion.back()
    }
    private fun panel(name: String): LinearLayout {
        // A chooser returning to its parent refreshes that page without duplicating it.
        if(name!=mode && panelHistory.peekLast()?.name==name)popPanel()
        val current=overlay
        if(current!=null && mode!=name)panelHistory.addLast(PanelSnapshot(
            current,mode,activeScroll,drawerScroll,drawerRows,search,
            openApprovalToken,approvalStateLabel,approvalActions.toList(),detailTarget
        ))
        detachPanel(); hideKeyboard(); mode=name; activeScroll=null
        val shade=FrameLayout(this).apply { background=DragonTheme.backdrop(this@MainActivity,true) }
        val page=PanelLayout(this,watchLayout.pageBottom).apply {
            setPadding(watchLayout.pageSide,watchLayout.top,watchLayout.pageSide,watchLayout.pageBottom); isClickable=true
        }
        shade.addView(page,FrameLayout.LayoutParams(-1,-1))
        root.addView(shade,FrameLayout.LayoutParams(-1,-1)); overlay=shade
        if(resumed && backMotion.enabled(shade)) {
            shade.alpha=.92f;shade.translationX=dp(12).toFloat()
            shade.animate().alpha(1f).translationX(0f).setDuration(180).start()
        }

        return page
    }
    private fun headerRow(page:LinearLayout,label:String,left:View,right:View?=null) {
        val top=row()
        top.setPadding(watchLayout.headerInset-watchLayout.pageSide,0,watchLayout.headerInset-watchLayout.pageSide,0)
        top.addView(left,LinearLayout.LayoutParams(watchLayout.button,watchLayout.button))
        top.addView(text(label,13f,ink,true).apply {
            gravity=Gravity.CENTER;maxLines=1;ellipsize=TextUtils.TruncateAt.END
        },LinearLayout.LayoutParams(0,-1,1f))
        top.addView(right ?: View(this),LinearLayout.LayoutParams(watchLayout.button,watchLayout.button))
        page.addView(top,LinearLayout.LayoutParams(-1,watchLayout.button))
    }
    private fun pageHeader(page: LinearLayout, label: String) {
        headerRow(page,label,icon("back","返回上一页") { navigateBack() })
    }

    private fun openDrawer() {
        val page=panel("drawer")
        headerRow(page,"聊天",icon("back","关闭历史对话") { closeOverlay() },icon("new","新建对话") { newChat() })
        search=EditText(this).apply {
            setText(drawerQuery); hint="搜索聊天"; textSize=12f; setTextColor(ink); setHintTextColor(muted)
            background=shape(surface,16); setPadding(dp(10),0,dp(8),0); isSingleLine=true; contentDescription="搜索历史对话"
            addTextChangedListener(object:TextWatcher {
                override fun beforeTextChanged(s:CharSequence?,start:Int,count:Int,after:Int){}
                override fun onTextChanged(s:CharSequence?,start:Int,before:Int,count:Int) { drawerQuery=s.toString(); ui.removeCallbacks(searchLater); ui.postDelayed(searchLater,400) }
                override fun afterTextChanged(s:Editable?){}
            })
        }
        val field=search!!
        field.visibility=if(drawerSearchExpanded || drawerQuery.isNotBlank())View.VISIBLE else View.GONE
        val tabs=row().apply { background=shape(0xC0252035.toInt(),14);setPadding(dp(2),dp(2),dp(2),dp(2)) }
        for((key,label) in listOf("all" to "全部","pinned" to "置顶","archived" to "归档")) {
            tabs.addView(text(label,10f,if(drawerTab==key)accent else muted).apply {
                gravity=Gravity.CENTER; background=shape(if(drawerTab==key)0xFF493B61.toInt() else Color.TRANSPARENT,12); contentDescription="会话分类：$label"; isSelected=drawerTab==key; isClickable=true
                setOnClickListener { drawerTab=key; openDrawer() }
            },LinearLayout.LayoutParams(0,dp(28),1f))
        }
        val tools=row()
        tools.addView(tabs,LinearLayout.LayoutParams(0,dp(32),1f))
        val searchButton=icon(if(field.visibility==View.VISIBLE)"close" else "search",if(field.visibility==View.VISIBLE)"清除并关闭搜索" else "搜索聊天") {}
        searchButton.setOnClickListener {
            drawerSearchExpanded=field.visibility!=View.VISIBLE
            field.visibility=if(drawerSearchExpanded)View.VISIBLE else View.GONE
            searchButton.glyph=if(drawerSearchExpanded)"close" else "search"
            searchButton.contentDescription=if(drawerSearchExpanded)"清除并关闭搜索" else "搜索聊天";searchButton.invalidate()
            if(drawerSearchExpanded) {
                field.requestFocus();field.post { (getSystemService(Context.INPUT_METHOD_SERVICE) as InputMethodManager).showSoftInput(field,InputMethodManager.SHOW_IMPLICIT) }
            } else { field.setText("");hideKeyboard() }
        }
        tools.addView(searchButton,LinearLayout.LayoutParams(watchLayout.button,watchLayout.button).apply { leftMargin=dp(4) })
        page.addView(tools,LinearLayout.LayoutParams(-1,watchLayout.button).apply { topMargin=dp(4) })
        page.addView(field,LinearLayout.LayoutParams(-1,dp(30)).apply { bottomMargin=dp(4) })
        drawerScroll=scrollView(); drawerRows=column(); drawerScroll!!.addView(drawerRows)
        page.addView(drawerScroll,LinearLayout.LayoutParams(-1,0,1f))
        drawerItems=JSONArray(); drawerCursor=null; loadDrawer(true)
    }
    private fun loadDrawer(reset: Boolean) {
        val query=drawerQuery; val tab=drawerTab; val generation=++drawerRequest
        ui.removeCallbacks(drawerStatusLater)
        if(reset)drawerItems=JSONArray()
        drawerLoading=true; drawDrawerRows()
        val cursor=if(reset)null else drawerCursor
        work {
            val path="/api/conversations?tab=$tab&query="+URLEncoder.encode(query,"UTF-8")+(if(cursor==null)"" else "&cursor="+URLEncoder.encode(cursor,"UTF-8"))
            val value=requestClient().json(path)
            postResult {
                if(mode!="drawer" || generation!=drawerRequest)return@postResult
                val items=value.getJSONArray("conversations")
                drawerProjects=value.optJSONArray("projects") ?: JSONArray()
                for(i in 0 until items.length())drawerItems.put(items.getJSONObject(i))
                drawerCursor=if(value.isNull("nextCursor"))null else value.optString("nextCursor").ifEmpty { null }
                drawerLoading=false; drawDrawerRows(); ui.postDelayed(drawerStatusLater,5000)
            }
        }
    }
    private fun statusColor(item:JSONObject)=when(item.optString("status")) {
        "running"->DragonTheme.RUNNING; "waiting"->DragonTheme.WAITING; "unread"->DragonTheme.UNREAD; else->muted
    }
    private fun setStatusLabel(label:TextView,item:JSONObject) {
        label.text=item.optString("statusLabel","状态未知")+(if(item.optBoolean("unread") && item.optString("status") in listOf("running","waiting"))" · 有新回复" else "")
        label.setTextColor(statusColor(item));label.background=shape((statusColor(item) and 0x00FFFFFF) or 0x20000000,8);label.contentDescription="会话状态：${label.text}"
    }
    private fun refreshDrawerStatuses() {
        if(!resumed || mode!="drawer" || drawerLoading)return
        val generation=drawerRequest; val drawer=overlay
        val ids=JSONArray()
        for(i in 0 until minOf(drawerItems.length(),1000))ids.put(drawerItems.getJSONObject(i).getString("threadId"))
        if(ids.length()==0)return
        work {
            try {
                val result=requestClient().json("/api/conversations/status",JSONObject().put("threadIds",ids)).getJSONObject("states")
                postResult {
                    if(mode!="drawer" || overlay!==drawer || generation!=drawerRequest)return@postResult
                    for(i in 0 until drawerItems.length()) {
                        val item=drawerItems.getJSONObject(i);val id=item.getString("threadId");val update=result.optJSONObject(id) ?: continue
                        for(key in listOf("status","statusLabel","busy","unread"))item.put(key,update.opt(key))
                        drawerStatusLabels[id]?.let { setStatusLabel(it,item) }
                    }
                    ui.postDelayed(drawerStatusLater,5000)
                }
            } catch(error:Exception) {
                postResult {
                    if(mode=="drawer" && overlay===drawer && generation==drawerRequest) {
                        drawerStatusLabels.values.forEach { it.text="状态暂不可刷新"; it.setTextColor(muted) }
                        ui.postDelayed(drawerStatusLater,10000)
                    }
                }
            }
        }
    }
    private fun drawDrawerRows() {
        val list=drawerRows ?: return
        val compact=prefs.getBoolean("ui.compactList",false)
        val scrollY=drawerScroll?.scrollY ?: 0
        list.removeAllViews();drawerStatusLabels.clear()
        val groups=linkedMapOf<String,MutableList<JSONObject>>()
        val names=mutableMapOf<String,String>()
        for(i in 0 until drawerProjects.length()) {
            val project=drawerProjects.getJSONObject(i);val id=project.getString("id")
            groups[id]=mutableListOf();names[id]=project.getString("name")
        }
        for(i in 0 until drawerItems.length()) {
            val item=drawerItems.getJSONObject(i)
            val key=if(item.isNull("projectId"))"" else item.optString("projectId")
            groups.getOrPut(key) { mutableListOf() }.add(item)
            names.putIfAbsent(key,if(key.isEmpty())"其他聊天" else item.optString("projectName","未识别项目"))
        }
        for((key,items) in groups) {
            if(items.isEmpty())continue
            val name=names[key] ?: "其他聊天"
            list.addView(text("$name · ${items.size}",12f,accent,true).apply { mark("folder",accent,13);setPadding(dp(4),dp(10),0,dp(6));contentDescription="项目分组：$name" })
            val expanded=expandedProjects.contains(key) || drawerQuery.isNotEmpty()
            for(item in if(expanded)items else items.take(3)) {
                val id=item.getString("threadId");val title=item.getString("title")
                val itemRow=row().apply { background=shape(if(id==currentThreadId())0xF03B304F.toInt() else 0xC01B182A.toInt(),12); setPadding(dp(7),dp(if(compact)3 else 5),0,dp(if(compact)3 else 5)) }
                val content=column().apply {
                    contentDescription="打开对话：$title"; minimumHeight=dp(if(compact)34 else 44); gravity=Gravity.CENTER_VERTICAL
                    setOnClickListener { linkChat(id) }
                    setOnLongClickListener { showConversationDetail(DetailTarget(id,JSONObject(item.toString()))); true }
                }
                content.addView(text((if(item.optBoolean("pinned"))"★ " else "")+title,12f).apply { maxLines=if(compact)1 else 2;ellipsize=TextUtils.TruncateAt.END })
                val status=text("",9f,muted).apply { setPadding(dp(6),dp(2),dp(6),dp(2)) }
                setStatusLabel(status,item);drawerStatusLabels[id]=status;content.addView(status,LinearLayout.LayoutParams(-2,-2).apply { topMargin=dp(4) })
                itemRow.addView(content,LinearLayout.LayoutParams(0,-2,1f))
                itemRow.addView(icon("more","对话详情：$title") { showConversationDetail(DetailTarget(id,JSONObject(item.toString()))) },LinearLayout.LayoutParams(dp(36),dp(42)))
                list.addView(itemRow,LinearLayout.LayoutParams(-1,-2).apply { bottomMargin=dp(3) })
            }
            if(items.size>3 && drawerQuery.isEmpty())list.addView(action(if(expanded)"收起 $name" else "展开 $name（${items.size-3}）") {
                if(!expandedProjects.add(key))expandedProjects.remove(key)
                drawDrawerRows()
            })
        }
        if(drawerLoading)list.addView(text("正在读取…",11f,muted).apply { gravity=Gravity.CENTER; setPadding(0,dp(14),0,0) })
        else if(drawerItems.length()==0)list.addView(text("没有找到聊天",12f,muted).apply { gravity=Gravity.CENTER; setPadding(0,dp(14),0,0) })
        if(!drawerLoading && drawerCursor!=null)list.addView(action("加载更多") { loadDrawer(false) })
        drawerScroll?.post { drawerScroll?.scrollTo(0,scrollY) }
    }

    private fun createContextControls() {
        projectText=action("") { if(currentThreadId().isBlank())projectPicker(false) else toast("当前项目："+state.optString("projectName","其他聊天")) }.apply {
            mark("folder");maxLines=2;ellipsize=TextUtils.TruncateAt.END
        }
        modelText=text("跟随电脑 · 默认 ⌄",10f,muted).apply {
            gravity=Gravity.CENTER;maxLines=1;ellipsize=TextUtils.TruncateAt.END;contentDescription="模型与思考强度"
            isClickable=true;isFocusable=true;setOnClickListener { openModels() }
            background=android.graphics.drawable.RippleDrawable(android.content.res.ColorStateList.valueOf(0x44D5BEF7),null,shape(Color.WHITE,18))
        }
    }
    private fun conversationInfo() {
        showConversationDetail(DetailTarget(currentThreadId(),JSONObject(state.toString())))
    }
    private fun showConversationDetail(target:DetailTarget) {
        val page=panel("context");detailTarget=target;pageHeader(page,"对话详情")
        val scroll=scrollView();val list=column()
        val data=target.data;val current=target.id==currentThreadId()
        list.addView(text(data.optString("title","新对话"),14f,ink,true).apply { setPadding(dp(4),dp(8),dp(4),dp(8)) })
        list.addView(text((computers.active()?.name ?: "未连接电脑")+" · "+if(current)statusText.text else data.optString("statusLabel","历史对话"),10f,muted).apply { setPadding(dp(4),0,dp(4),dp(6)) })
        if(current && (state.optJSONArray("approvals")?.length() ?: 0)>0)list.addView(action("待确认操作",true) { approvalList() })
        if(current && target.id.isEmpty()) {
            (projectText.parent as? ViewGroup)?.removeView(projectText);list.addView(projectText)
        } else list.addView(text("项目："+data.optString("projectName").ifBlank { "其他聊天" },11f,muted).apply { setPadding(dp(4),dp(4),dp(4),dp(8)) })
        if(target.id.isNotEmpty()) {
            list.addView(action("重命名") { renamePage(target.id,data.optString("title","")) })
            list.addView(action(if(data.optBoolean("pinned"))"取消置顶" else "置顶") { manage(target.id,if(data.optBoolean("pinned"))"unpin" else "pin") })
            list.addView(action(if(data.optBoolean("archived"))"恢复对话" else "归档对话") {
                if(data.optBoolean("archived"))manage(target.id,"restore") else {
                    val confirm=panel("confirm");pageHeader(confirm,"归档对话")
                    confirm.addView(text("归档“${data.optString("title") }”？聊天记录和草稿会保留。",12f,muted))
                    confirm.addView(action("归档",true) { manage(target.id,"archive") })
                    confirm.addView(action("取消") { navigateBack() })
                }
            })
            list.addView(action("在电脑打开") { work { requestClient().json("/api/conversation/open",JSONObject().put("threadId",target.id));postResult { toast("已在电脑打开") } } })
        }
        val error=localError.ifEmpty { state.optString("error") }
        if(error.isNotEmpty())list.addView(text(error,11f,DragonTheme.WAITING))
        scroll.addView(list);page.addView(scroll,LinearLayout.LayoutParams(-1,0,1f));updateControls()
    }
    private fun choices(title: String, labels: List<String>, choose: (Int) -> Unit) {
        val page=panel("menu"); pageHeader(page,title)
        val scroll=scrollView(); val list=column()
        val chooser=overlay
        labels.forEachIndexed { index,label -> list.addView(action(label) {
            choose(index)
            if(overlay===chooser)popPanel()
        }) }
        scroll.addView(list); page.addView(scroll,LinearLayout.LayoutParams(-1,0,1f))
    }
    private fun renamePage(id: String, name: String) {
        val page=panel("rename"); pageHeader(page,"重命名")
        val scroll=scrollView(); val list=column()
        val field=EditText(this).apply {
            setText(name); textSize=12f; setTextColor(ink); setHintTextColor(muted); hint="对话名称"; maxLines=3
            setSelectAllOnFocus(true); contentDescription="对话名称"; background=shape(surface,12); setPadding(dp(10),dp(8),dp(10),dp(8))
            imeOptions=EditorInfo.IME_FLAG_NO_EXTRACT_UI
        }
        list.addView(field,LinearLayout.LayoutParams(-1,-2).apply { topMargin=dp(8) })
        list.addView(action("保存名称",true) {
            val title=field.text.toString().trim()
            if(title.isEmpty())toast("请输入名称") else { hideKeyboard();manage(id,"rename",title) }
        })
        scroll.addView(list); page.addView(scroll,LinearLayout.LayoutParams(-1,0,1f))
    }
    private fun manage(id: String, operation: String, title: String?=null) {
        if(!resumed || managing)return
        managing=true
        work {
            try { requestClient().json("/api/conversation/action",JSONObject().put("threadId",id).put("action",operation).put("title",title)) }
            catch(error:Exception) { postResult { managing=false;toast(error.message ?: "操作失败，请重试") };return@work }
            postResult {
                managing=false
                toast(when(operation) { "rename"->"名称已同步到电脑"; "pin"->"已置顶"; "unpin"->"已取消置顶"; "archive"->"已归档"; else->"已恢复" })
                detailTarget?.takeIf { it.id==id }?.let { target ->
                    when(operation) { "rename"->target.data.put("title",title);"pin","unpin"->target.data.put("pinned",operation=="pin");"archive","restore"->target.data.put("archived",operation=="archive") }
                    if(operation=="archive" && id==currentThreadId()) { closeOverlay();openDrawer() }
                    else { if(mode!="context")popPanel();showConversationDetail(target) }
                }
                fetch();if(mode=="drawer")loadDrawer(true)
            }
        }
    }
    private fun messageMenu(id: String) {
        val messages=state.optJSONArray("messages") ?: return
        val message=(0 until messages.length()).map { messages.getJSONObject(it) }.firstOrNull { it.optString("id")==id } ?: return
        val assistant=message.optString("role")=="assistant"
        val choices=if(assistant)arrayOf("复制","朗读回复","引用到输入框","重新提问") else arrayOf("复制","放入输入框")
        choices("消息操作",choices.toList()) { option ->
            when {
                option==0 -> { (getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager).setPrimaryClip(ClipData.newPlainText("聊天消息",message.getString("text"))); toast("已复制") }
                assistant && option==1 -> speak(id)
                assistant && option==3 -> {
                    val user=(messages.length()-1 downTo 0).map { messages.getJSONObject(it) }.firstOrNull { it.optString("role")=="user" }
                    if(user!=null)input.setText(user.getString("text"))
                }
                else -> { input.setText(if(assistant)"引用："+message.getString("text")+"\n\n" else message.getString("text")); input.setSelection(input.text.length) }
            }
        }
    }

    private fun openModels() {
        modelsSaving=false
        val generation=++modelRequest
        val settings=state.optJSONObject("settings") ?: JSONObject()
        selectedModel=settings.optString("model"); selectedEffort=settings.optString("thinking")
        val page=panel("models"); pageHeader(page,"模型与思考")
        page.addView(text("正在读取可用模型…",12f,muted))
        work {
            try {
                val result=requestClient().json("/api/models")
                postResult { if(mode=="models" && generation==modelRequest) { models=result.getJSONArray("models");drawModels() } }
            } catch(error:Exception) {
                postResult { if(mode=="models" && generation==modelRequest) {
                    val retry=panel("models");pageHeader(retry,"模型与思考")
                    retry.addView(text(error.message ?: "模型读取失败",12f,muted))
                    retry.addView(action("重新读取模型") { openModels() })
                } }
            }
        }
    }
    private fun effortName(value:String) = when(value) { "low"->"轻量"; "medium"->"均衡"; "high"->"深入"; "xhigh"->"更深入"; "max"->"最高"; "ultra"->"极致"; else->value }
    private fun drawModels() {
        val position=if(mode=="models")activeScroll?.scrollY ?: 0 else 0
        val page=panel("models"); pageHeader(page,"模型与思考")
        val scroll=scrollView(); val list=column()
        list.addView(text("选择后，下次发送生效",10f,muted).apply { gravity=Gravity.CENTER })
        if(models.length()==0)list.addView(text("电脑暂未提供可选模型，仍可跟随电脑。",11f,muted))
        list.addView(action((if(selectedModel.isEmpty())"✓ " else "")+"跟随电脑") { selectedModel=""; selectedEffort=""; drawModels() })
        for(i in 0 until models.length()) {
            val model=models.getJSONObject(i); val id=model.getString("id")
            list.addView(action((if(selectedModel==id)"✓ " else "")+model.getString("name")) { selectedModel=id; selectedEffort=""; drawModels() })
        }
        val chosen=(0 until models.length()).map { models.getJSONObject(it) }.firstOrNull { it.getString("id")==selectedModel }
        if(selectedModel.isNotBlank() && chosen==null)list.addView(text("当前模型暂不可选，请选择其他模型或跟随电脑。",11f,muted))
        if(chosen!=null) {
            list.addView(text("思考强度",12f,accent,true).apply { setPadding(0,dp(14),0,dp(3)) })
            list.addView(action((if(selectedEffort.isEmpty())"✓ " else "")+"模型默认") { selectedEffort=""; drawModels() })
            val efforts=chosen.getJSONArray("efforts")
            for(i in 0 until efforts.length()) { val value=efforts.getString(i); list.addView(action((if(selectedEffort==value)"✓ " else "")+effortName(value)) { selectedEffort=value; drawModels() }) }
        }
        scroll.addView(list); page.addView(scroll,LinearLayout.LayoutParams(-1,0,1f))
        for(i in 0 until list.childCount)list.getChildAt(i).isEnabled=!modelsSaving
        scroll.post { scroll.scrollTo(0,position) }
        page.addView(action(if(modelsSaving)"正在保存…" else "保存",true) {
            if(modelsSaving)return@action
            val selected=sessionId
            val model=selectedModel;val effort=selectedEffort
            modelsSaving=true;drawModels()
            work {
                try {
                    val value=requestClient().json("/api/session/settings",JSONObject().put("sessionId",selected).put("model",model).put("thinking",effort))
                    postResult { modelsSaving=false;if(selected==sessionId) { state=value;if(mode=="models")popPanel();updateControls();toast("已保存，下次发送生效") } }
                } catch(error:Exception) { postResult { modelsSaving=false;if(mode=="models" && selected==sessionId) { drawModels();toast(error.message ?: "保存失败，请重试") } } }
            }
        }.apply { isEnabled=!modelsSaving })
    }

    private fun settingsPage() {
        val page=panel("settings"); pageHeader(page,"设置")
        val scroll=scrollView(); val list=column()
        list.addView(action(if(prefs.getBoolean("autoRead",false))"自动朗读：开启" else "自动朗读：关闭") { prefs.edit().putBoolean("autoRead",!prefs.getBoolean("autoRead",false)).apply(); settingsPage() })
        list.addView(navigation("外观与阅读") { appearancePage() })
        list.addView(navigation("电脑连接") { computersPage() })
        list.addView(navigation("操作与手势") { inputHelp() })
        list.addView(action("触感反馈："+if(prefs.getBoolean("ui.haptics",true))"开启" else "关闭") { prefs.edit().putBoolean("ui.haptics",!prefs.getBoolean("ui.haptics",true)).apply();settingsPage() })
        list.addView(text("回复时发送位会变成停止按钮。需要选择时自动弹出确认窗口；关闭后可从对话详情重新打开。",11f,muted).apply { setPadding(0,dp(14),0,dp(8)) })
        list.addView(text("WatchChat 0.13.0 · 龙娘主题",10f,muted).apply { gravity=Gravity.CENTER })
        scroll.addView(list); page.addView(scroll,LinearLayout.LayoutParams(-1,0,1f))
    }
    private fun refreshAppearance() {
        root.background=DragonTheme.backdrop(this)
        overlay?.background=DragonTheme.backdrop(this,true)
        panelHistory.forEach { it.view.background=DragonTheme.backdrop(this,true) }
        updateMessages(true)
    }
    private fun appearancePage() {
        val page=panel("appearance");pageHeader(page,"外观与阅读")
        val scroll=scrollView();val list=column()
        fun toggle(key:String,label:String,on:String,off:String) {
            list.addView(action(label+"："+if(prefs.getBoolean(key,false))on else off) {
                prefs.edit().putBoolean(key,!prefs.getBoolean(key,false)).apply()
                refreshAppearance();appearancePage()
            })
        }
        toggle("ui.quietBackground","背景","纯净阅读","龙娘插画")
        toggle("ui.deepBackground","背景明暗","加深","标准")
        toggle("ui.compactList","历史列表","紧凑","舒适")
        list.addView(action("字体："+when(prefs.getInt("fontSize",13)) { 12->"较小";15->"较大";else->"标准" }) {
            choices("聊天字号",listOf("较小","标准","较大")) { i ->
                prefs.edit().putInt("fontSize",listOf(12,13,15)[i]).apply();updateMessages(true);appearancePage()
            }
        })
        list.addView(text("立即生效，并在下次打开时保留。纯净背景适合长文阅读；插画背景保持静态。",10f,muted).apply { setPadding(dp(4),dp(10),dp(4),dp(8)) })
        scroll.addView(list);page.addView(scroll,LinearLayout.LayoutParams(-1,0,1f))
    }
    private fun inputHelp() {
        val page=panel("input-help");pageHeader(page,"操作与手势")
        val scroll=scrollView();val list=column()
        for((title,description) in listOf(
            "旋转表冠" to "滚动当前聊天、历史列表或面板，无需先点列表。",
            "历史对话" to "只点击左上角菜单打开，横向滑动不会展开。",
            "查看额度" to "从聊天页顶部向下滑动打开；消息区上下滑动仍然只滚动聊天。",
            "停止与确认" to "回复中发送位变成停止方块，结束后恢复发送。需要选择时自动弹窗，关闭后可从对话详情重新打开。",
            "滑动返回" to "左滑或右滑逐级返回上一页，聊天首页再滑动才退出。也可点击左上角返回；输入框内滑动不触发返回。",
            "双击聊天区" to "回到最新消息。输入框和操作按钮不触发此手势。",
            "长按消息" to "打开复制、朗读、引用等操作。",
            "表冠按下" to "由手表系统处理，保留返回或应用列表功能。"
        )) { list.addView(text(title,12f,accent,true).apply { setPadding(0,dp(12),0,dp(4)) });list.addView(text(description,11f,muted)) }
        scroll.addView(list);page.addView(scroll,LinearLayout.LayoutParams(-1,0,1f))
    }
    private fun usagePage(force: Boolean=false) {
        val page=panel("usage"); pageHeader(page,"账号额度")
        val scroll=scrollView(); val list=column()
        val loading=text("正在读取电脑账号额度…",11f,muted).apply { gravity=Gravity.CENTER; setPadding(0,dp(24),0,dp(12)) }
        list.addView(loading);scroll.addView(list);page.addView(scroll,LinearLayout.LayoutParams(-1,0,1f))
        fun percent(value:Double)=if(value%1.0==0.0)value.toInt().toString() else String.format(Locale.CHINA,"%.1f",value)
        fun windowName(minutes:Int)=when { minutes==10080->"每周额度"; minutes==300->"5小时额度"; minutes>0 && minutes%1440==0->"${minutes/1440}天额度"; minutes>0 && minutes%60==0->"${minutes/60}小时额度"; minutes>0->"${minutes}分钟额度"; else->"用量额度" }
        fun date(value:Long)=SimpleDateFormat("M月d日 HH:mm",Locale.CHINA).format(Date(value*1000))
        work {
            try {
                val value=requestClient().json("/api/usage"+if(force)"?refresh=1" else "")
                postResult {
                    if(mode!="usage" || overlay==null)return@postResult
                    list.removeAllViews()
                    if(value.optBoolean("stale"))list.addView(text(value.optString("error"),10f,Color.rgb(242,173,146)).apply { setPadding(0,dp(5),0,dp(8)) })
                    val groups=value.optJSONArray("groups") ?: JSONArray()
                    if(groups.length()==0)list.addView(text("电脑暂未提供额度信息",12f,muted).apply { setPadding(0,dp(16),0,dp(16)) })
                    for(i in 0 until groups.length()) {
                        val group=groups.getJSONObject(i)
                        val plan=when(group.optString("planType")) { "prolite"->"Pro Lite"; "pro"->"Pro"; "plus"->"Plus"; "team"->"Team"; "business"->"Business"; "free"->"Free"; else->"" }
                        list.addView(text(group.optString("name","Codex")+(if(plan.isEmpty())"" else " · $plan"),12f,ink,true).apply { setPadding(0,dp(8),0,dp(6)) })
                        val windows=group.optJSONArray("windows") ?: JSONArray()
                        if(windows.length()==0)list.addView(text("暂无可用额度数据",11f,muted))
                        for(j in 0 until windows.length()) {
                            val window=windows.getJSONObject(j)
                            val card=column().apply { background=shape(surface,14); setPadding(dp(10),dp(10),dp(10),dp(10)) }
                            card.addView(text(windowName(window.optInt("windowDurationMins",0)),10f,muted))
                            card.addView(text(if(window.isNull("remainingPercent"))"剩余额度未知" else "剩余 ${percent(window.getDouble("remainingPercent"))}%",19f,accent,true).apply { setPadding(0,dp(5),0,dp(6)) })
                            if(!window.isNull("usedPercent"))card.addView(text("已用 ${percent(window.getDouble("usedPercent"))}%",10f,muted))
                            if(!window.isNull("resetsAt"))card.addView(text("重置："+date(window.getLong("resetsAt")),10f,ink).apply { setPadding(0,dp(5),0,0) })
                            list.addView(card,LinearLayout.LayoutParams(-1,-2).apply { bottomMargin=dp(8) })
                        }
                        if(group.optBoolean("limitReached"))list.addView(text("当前额度已达上限",11f,Color.rgb(242,173,146)))
                        val credits=group.optJSONObject("credits")
                        if(credits!=null)list.addView(text(if(credits.optBoolean("unlimited"))"额外点数：不限量" else if(credits.isNull("balance"))"额外点数：暂无信息" else "额外点数："+credits.optString("balance"),10f,muted).apply { setPadding(0,dp(3),0,dp(4)) })
                    }
                    if(!value.isNull("availableResetCount"))list.addView(text("可用额度重置：${value.optInt("availableResetCount")}次",10f,muted).apply { setPadding(0,dp(6),0,dp(4)) })
                    val time=runCatching { java.time.Instant.parse(value.optString("updatedAt")).epochSecond }.getOrNull()
                    if(time!=null)list.addView(text("更新："+date(time),9f,muted))
                    list.addView(text("这是账号共享额度，两端用量合并计算。",10f,muted).apply { setPadding(0,dp(9),0,dp(4)) })
                    list.addView(action("刷新额度",true) { usagePage(true) })
                }
            } catch(error:Exception) {
                postResult { if(mode=="usage") { loading.text=error.message ?: "读取额度失败"; list.addView(action("重新读取",true) { usagePage(true) }) } }
            }
        }
    }
    private fun interruptReply() {
        if(controlling || !state.optBoolean("canInterrupt"))return
        val selected=sessionId; val turn=state.optString("turnId")
        if(turn.isEmpty() || turn=="null") { fetch(); return }
        controlling=true; localError=""; updateControls()
        work {
            val result=requestClient().json("/api/interrupt",JSONObject().put("sessionId",selected).put("turnId",turn))
            postResult { controlling=false; if(selected==sessionId) { state=result.getJSONObject("state"); localError=""; updateMessages(); updateControls(); toast(if(result.optJSONObject("result")?.optBoolean("alreadyFinished")==true)"这次回复已经结束" else "已停止本次回复") } }
        }
    }
    private fun approvalList() {
        val items=state.optJSONArray("approvals") ?: JSONArray()
        if(items.length()==0) { toast("当前没有待确认操作"); fetch(); return }
        if(items.length()==1) { approvalPage(items.getJSONObject(0)); return }
        choices("待确认操作",(0 until items.length()).map { items.getJSONObject(it).optString("title") }) { approvalPage(items.getJSONObject(it)) }
    }
    private fun approvalPage(item: JSONObject) {
        val selected=sessionId; val token=item.getString("token")
        val page=panel("approval"); pageHeader(page,item.optString("title","待确认"))
        openApprovalToken=token
        val scroll=scrollView(); val list=column(); val answers=JSONObject()
        val details=item.optString("details")
        if(details.isNotEmpty())list.addView(text(details,11f).apply { setPadding(0,dp(8),0,dp(12)); setTextIsSelectable(true) })
        val questions=item.optJSONArray("questions") ?: JSONArray()
        for(i in 0 until questions.length()) {
            val question=questions.getJSONObject(i); val id=question.getString("id")
            list.addView(text(question.optString("question",question.optString("header")),12f,ink,true).apply { setPadding(0,dp(10),0,dp(5)) })
            val options=question.optJSONArray("options") ?: JSONArray(); val optionViews=mutableListOf<TextView>()
            var field: EditText?=null
            for(j in 0 until options.length()) {
                val option=options.getJSONObject(j); val label=option.getString("label"); val description=option.optString("description")
                val button=action(label+(if(description.isEmpty())"" else "\n"+description)) {
                    answers.put(id,label); field?.setText("")
                    optionViews.forEachIndexed { index,view -> view.setTextColor(if(index==j)accent else ink); view.background=shape(if(index==j)0xFF3B304F.toInt() else surface,18) }
                }
                optionViews.add(button);list.addView(button)
            }
            if(options.length()==0 || question.optBoolean("isOther")) {
                field=EditText(this).apply {
                    textSize=12f; setTextColor(ink); setHintTextColor(muted); hint=if(options.length()>0)"或填写其他回答" else "填写回答"; contentDescription="回答：$id"
                    background=shape(surface,12); setPadding(dp(9),dp(8),dp(9),dp(8)); minLines=1; maxLines=4
                    imeOptions=EditorInfo.IME_FLAG_NO_EXTRACT_UI
                    if(question.optBoolean("isSecret"))inputType=129
                    else if(question.optString("valueType") in listOf("number","integer"))inputType=android.text.InputType.TYPE_CLASS_NUMBER or android.text.InputType.TYPE_NUMBER_FLAG_DECIMAL or android.text.InputType.TYPE_NUMBER_FLAG_SIGNED
                    addTextChangedListener(object:TextWatcher {
                        override fun beforeTextChanged(s:CharSequence?,start:Int,count:Int,after:Int){}
                        override fun onTextChanged(s:CharSequence?,start:Int,before:Int,count:Int) { if(!s.isNullOrEmpty()) { answers.put(id,s.toString()); optionViews.forEach { it.setTextColor(ink); it.background=shape(surface,18) } } else if((0 until options.length()).none { options.getJSONObject(it).optString("label")==answers.optString(id) })answers.remove(id) }
                        override fun afterTextChanged(s:Editable?){}
                    })
                }
                list.addView(field,LinearLayout.LayoutParams(-1,-2).apply { topMargin=dp(6) })
            }
        }
        approvalStateLabel=text("选择后会同步到电脑",9f,muted).apply { gravity=Gravity.CENTER; setPadding(0,dp(10),0,dp(5)) }
        list.addView(approvalStateLabel)
        val actions=item.optJSONArray("actions") ?: JSONArray()
        for(i in 0 until actions.length()) {
            val value=actions.getJSONObject(i); val actionId=value.getString("id")
            val button=action(value.getString("label"),actionId=="accept" || actionId=="answer") {
                if(controlling || selected!=sessionId)return@action
                if(actionId=="answer") {
                    val missing=(0 until questions.length()).map { questions.getJSONObject(it) }.any { q -> q.optBoolean("required",true) && answers.optString(q.getString("id")).isBlank() }
                    if(missing) { toast("请完成所有必填问题"); return@action }
                }
                controlling=true; localError=""; hideKeyboard(); updateControls()
                work {
                    try {
                        val response=requestClient().json("/api/approval",JSONObject().put("sessionId",selected).put("token",token).put("action",actionId).put("answers",if(actionId=="answer")answers else JSONObject.NULL))
                        postResult {
                            controlling=false
                            if(selected==sessionId) { state=response.getJSONObject("state"); localError=""; closeOverlay(); updateMessages(); updateControls(); toast("已同步确认结果") }
                        }
                    } catch(error:Exception) {
                        postResult { controlling=false; localError=error.message?.take(180) ?: "提交失败，请刷新"; updateControls(); toast(localError); fetch() }
                    }
                }
            }
            approvalActions.add(button);list.addView(button)
        }
        scroll.addView(list);page.addView(scroll,LinearLayout.LayoutParams(-1,0,1f));updateControls();showApprovalDialog()
    }
    private fun showApprovalDialog() {
        val shade=overlay ?: return
        (shade.parent as? ViewGroup)?.removeView(shade)
        val dialog=object:Dialog(this,R.style.WatchChatTheme) {
            private var startX=0f; private var startY=0f
            private var eligible=false; private var claimed=false
            @Deprecated("Dialog back delegates to the page stack")
            override fun onBackPressed() { navigateBack() }
            override fun dispatchGenericMotionEvent(event: MotionEvent): Boolean {
                if(window?.decorView?.rootWindowInsets?.isVisible(WindowInsets.Type.ime())==true)
                    return super.dispatchGenericMotionEvent(event)
                if(event.action==MotionEvent.ACTION_SCROLL && event.isFromSource(InputDevice.SOURCE_ROTARY_ENCODER))
                    return this@MainActivity.dispatchGenericMotionEvent(event)
                return super.dispatchGenericMotionEvent(event)
            }
            override fun dispatchTouchEvent(event:MotionEvent):Boolean {
                if((getSystemService(Context.ACCESSIBILITY_SERVICE) as AccessibilityManager).isTouchExplorationEnabled)return super.dispatchTouchEvent(event)
                if(backMotion.settling)return true
                if(event.actionMasked==MotionEvent.ACTION_DOWN) {
                    startX=event.rawX; startY=event.rawY; claimed=false
                    eligible=!onInteractiveControl(shade,event.rawX.toInt(),event.rawY.toInt(),true)
                }
                if(event.pointerCount>1)eligible=false
                val dx=event.rawX-startX; val dy=event.rawY-startY
                if(event.actionMasked==MotionEvent.ACTION_MOVE && eligible && !claimed) {
                    if(kotlin.math.abs(dy)>dp(18) && kotlin.math.abs(dy)>=kotlin.math.abs(dx))eligible=false
                    else if(kotlin.math.abs(dx)>dp(18) && kotlin.math.abs(dx)>kotlin.math.abs(dy)*1.5f) {
                        claimed=true
                        val cancel=MotionEvent.obtain(event).apply { action=MotionEvent.ACTION_CANCEL }
                        super.dispatchTouchEvent(cancel); cancel.recycle()
                    }
                }
                if(claimed) {
                    if(event.actionMasked==MotionEvent.ACTION_MOVE)backMotion.drag(dx)
                    if(event.actionMasked==MotionEvent.ACTION_UP || event.actionMasked==MotionEvent.ACTION_CANCEL) {
                        val back=event.actionMasked==MotionEvent.ACTION_UP && eligible && kotlin.math.abs(dx)>=dp(64) && kotlin.math.abs(dx)>kotlin.math.abs(dy)*1.5f
                        claimed=false;backMotion.finish(back)
                    }
                    return true
                }
                return super.dispatchTouchEvent(event)
            }
        }
        approvalDialog=dialog
        dialog.setContentView(shade); dialog.setCanceledOnTouchOutside(false); dialog.show()
        dialog.window?.apply {
            clearFlags(WindowManager.LayoutParams.FLAG_DIM_BEHIND)
            setDecorFitsSystemWindows(false);setBackgroundDrawableResource(android.R.color.transparent);setLayout(-1,-1)
            insetsController?.hide(WindowInsets.Type.statusBars())
        }
    }
    private fun computersPage() {
        val page=panel("computers"); pageHeader(page,"电脑连接")
        val scroll=scrollView(); val list=column()
        list.addView(text("选择当前要连接的电脑",11f,muted).apply { setPadding(0,dp(6),0,dp(8)) })
        for(profile in computers.all()) {
            val item=row()
            val host=if(profile.mode=="public")"公网 · "+runCatching { java.net.URI(profile.url).host }.getOrDefault("") else "局域网"
            item.addView(action((if(profile.id==computers.activeId())"✓ " else "")+profile.name+"\n"+host) {
                runCatching { connectComputer(profile) }.onFailure { toast(it.message ?: "连接信息不正确") }
            },LinearLayout.LayoutParams(0,-2,1f))
            item.addView(icon("more","编辑电脑：${profile.name}") { connectionSettings(profile) },LinearLayout.LayoutParams(dp(30),dp(40)))
            list.addView(item)
        }
        list.addView(action("局域网扫描",true) { lanScanPage() })
        list.addView(action("公网连接") { publicConnectionPage() })
        list.addView(text("两种模式可连接同一台电脑，对话和草稿继续保留。首次配对需在电脑核对并允许。",10f,muted).apply { setPadding(0,dp(10),0,0) })
        scroll.addView(list); page.addView(scroll,LinearLayout.LayoutParams(-1,0,1f))
    }
    private fun connectionSettings(profile: ComputerProfile?=null) {
        if(profile==null) { publicConnectionPage();return }
        val page=panel("connection-options");pageHeader(page,profile.name)
        val scroll=scrollView();val list=column()
        list.addView(action("局域网模式") {
            runCatching { connectComputer(profile.using("lan")) }.onFailure { lanScanPage(profile.id) }
        })
        list.addView(action("公网模式") {
            if(profile.publicUrl.isNotEmpty() || profile.mode=="public")runCatching { connectComputer(profile.using("public")) }.onFailure { toast(it.message ?: "连接失败") }
            else publicConnectionPage(profile)
        })
        list.addView(action("重新扫描局域网") { lanScanPage(profile.id) })
        list.addView(action("配置公网域名") { publicConnectionPage(profile) })
        list.addView(action("手动配置（高级）") { manualConnectionSettings(profile) })
        scroll.addView(list);page.addView(scroll,LinearLayout.LayoutParams(-1,0,1f))
    }
    private fun manualConnectionSettings(profile: ComputerProfile?=null) {
        val page=panel("connection"); pageHeader(page,if(profile==null)"添加电脑" else "修改电脑")
        val scroll=scrollView(); val list=column()
        fun field(hint:String,initial:String,secret:Boolean=false):EditText {
            val value=EditText(this).apply {
                this.hint=hint; setText(initial); textSize=11f; setTextColor(ink); setHintTextColor(muted)
                if(secret)inputType=129
                maxLines=3
                background=shape(surface,12);setPadding(dp(10),dp(8),dp(10),dp(8))
            }
            list.addView(value,LinearLayout.LayoutParams(-1,-2)); return value
        }
        val name=field("电脑名称",profile?.name ?: "")
        val url=field("https://电脑地址:8766",profile?.url ?: "")
        val token=field("连接口令",profile?.token ?: "",true)
        val pin=field("电脑证书指纹",profile?.pin ?: "")
        list.addView(action("保存并连接",true) {
            runCatching {
                connectComputer(ComputerProfile(profile?.id ?: UUID.randomUUID().toString(),name.text.toString().trim(),
                    url.text.toString().trim(),token.text.toString().trim(),pin.text.toString().trim(),profile?.mode ?: "lan",profile?.lanUrl ?: "",profile?.publicUrl ?: ""))
            }.onFailure { toast(it.message ?: "连接信息不正确") }
        })
        scroll.addView(list); page.addView(scroll,LinearLayout.LayoutParams(-1,0,1f))
    }

    private fun stopConnectionTasks() { connectionEpoch++;lanDiscovery?.stop();lanDiscovery=null;pairingClient?.setForeground(false);pairingClient=null }
    private fun lanScanPage(onlyId:String?=null) {
        val page=panel("lan-scan");pageHeader(page,"局域网扫描")
        val scroll=scrollView();val list=column()
        val status=text("正在查找同一Wi-Fi的电脑…",11f,muted);list.addView(status)
        val results=column();list.addView(results)
        list.addView(action("重新扫描") { lanScanPage(onlyId) })
        list.addView(text("电脑需运行最新版连接服务。首次添加时，在电脑运行“开启电脑配对.cmd”。",10f,muted).apply { setPadding(0,dp(8),0,dp(6)) })
        list.addView(action("手动配置（高级）") { manualConnectionSettings() })
        scroll.addView(list);page.addView(scroll,LinearLayout.LayoutParams(-1,0,1f))
        val generation=connectionEpoch;val seen=mutableSetOf<String>()
        lanDiscovery=LanDiscovery(this,{ candidate ->
            if(mode=="lan-scan" && generation==connectionEpoch && (onlyId==null || candidate.id==onlyId) && seen.add(candidate.id)) {
                status.text="找到 ${seen.size} 台电脑"
                results.addView(action(candidate.name) {
                    val old=computers.all().firstOrNull { it.id==candidate.id }
                    if(old!=null)runCatching {
                        require(old.pin==candidate.pin) { "电脑证书已变化，请先核对并重新配对" }
                        connectComputer(old.copy(url=candidate.url,mode="lan",lanUrl=candidate.url,publicUrl=if(old.mode=="public")old.url else old.publicUrl))
                    }.onFailure { toast(it.message ?: "连接失败") }
                    else startPairing(candidate)
                })
            }
        },{ message -> if(mode=="lan-scan" && generation==connectionEpoch)status.text=if(seen.isEmpty())message+"\n未发现电脑" else message })
        lanDiscovery?.start()
    }
    private fun publicConnectionPage(profile:ComputerProfile?=null) {
        val page=panel("public-connect");pageHeader(page,"公网模式")
        val scroll=scrollView();val list=column()
        list.addView(text("输入已配置隧道的HTTPS域名",11f,muted).apply { setPadding(0,dp(8),0,dp(8)) })
        val domain=EditText(this).apply {
            hint="watch.example.com";textSize=12f;setTextColor(ink);setHintTextColor(muted);isSingleLine=true
            inputType=android.text.InputType.TYPE_CLASS_TEXT or android.text.InputType.TYPE_TEXT_VARIATION_URI
            setText(profile?.let { if(it.mode=="public")it.url else it.publicUrl } ?: "")
            background=shape(surface,12);setPadding(dp(10),dp(8),dp(10),dp(8));contentDescription="公网域名"
        }
        list.addView(domain,LinearLayout.LayoutParams(-1,dp(40)))
        list.addView(action("配对并连接",true) {
            runCatching { val url=ConnectionAddress.publicUrl(domain.text.toString());hideKeyboard();startPairing(ConnectionCandidate(profile?.id ?: "",profile?.name ?: "公网电脑",url,"", "public")) }
                .onFailure { toast(it.message ?: "域名无效") }
        })
        list.addView(text("电脑先运行公网隧道和“开启电脑配对.cmd”。未部署域名时，可先使用局域网扫描。",10f,muted).apply { setPadding(0,dp(10),0,dp(6)) })
        scroll.addView(list);page.addView(scroll,LinearLayout.LayoutParams(-1,0,1f))
    }
    private fun pairingPaused(target:ConnectionCandidate) {
        val page=panel("pair-device");pageHeader(page,"电脑配对")
        page.addView(text("配对已暂停",12f,muted).apply { gravity=Gravity.CENTER;setPadding(0,dp(16),0,dp(10)) })
        page.addView(action("重新开始配对",true) { startPairing(target) })
    }
    private fun startPairing(target:ConnectionCandidate) {
        val page=panel("pair-device");pageHeader(page,"电脑配对");pausedPairTarget=target
        val scroll=scrollView();val list=column()
        val label=text("正在连接 ${target.name}…",11f,muted);list.addView(label)
        val code=text("",19f,accent,true).apply { gravity=Gravity.CENTER;setPadding(0,dp(12),0,dp(12));contentDescription="配对核对码" };list.addView(code)
        val help=text("",11f,muted);list.addView(help)
        list.addView(action("取消配对") { navigateBack() })
        scroll.addView(list);page.addView(scroll,LinearLayout.LayoutParams(-1,0,1f))
        val generation=connectionEpoch
        val claim=UUID.randomUUID().toString()+UUID.randomUUID().toString();val requestId=UUID.randomUUID().toString()
        val transport=BridgeClient(target.url,claim,target.pin.ifBlank { "0".repeat(64) },mode=target.mode);pairingClient=transport
        fun current()=resumed && mode=="pair-device" && generation==connectionEpoch
        fun failure(error:Exception) { ui.post { if(current()) { label.text=error.message?.take(120) ?: "配对失败";help.text="请检查电脑连接服务和配对窗口，再返回重试。" } } }
        pool.execute {
            try {
                val info=transport.json("/api/connect/info");val id=info.getString("computerId");val pin=info.getString("certificateSha256")
                require(pin.matches(Regex("[a-f0-9]{64}")) && id.matches(Regex("[A-Za-z0-9_-]{1,100}"))) { "电脑身份信息无效" }
                require(target.id.isEmpty() || target.id==id) { "此地址对应另一台电脑" }
                require(target.mode!="lan" || target.pin==pin) { "电脑证书不一致" }
                require(info.optBoolean("pairingOpen")) { "请先在电脑运行“开启电脑配对.cmd”" }
                val hash=ConnectionAddress.hash(claim)
                transport.json("/api/connect/requests",JSONObject().put("requestId",requestId).put("claimHash",hash).put("mode",target.mode).put("url",target.url).put("deviceName","手表 chatgpt"))
                ui.post { if(current()) { label.text="请核对电脑上的同一组码";code.text=ConnectionAddress.code(id,pin,target.mode,target.url,requestId,hash);help.text="在电脑允许后会自动连接。\n配对有效期为3分钟。" } }
                val deadline=System.currentTimeMillis()+180000
                val pollPair=object:Runnable {
                    override fun run() {
                        if(!current())return
                        if(System.currentTimeMillis()>deadline) { label.text="配对已过期，请返回重试";return }
                        pool.execute {
                            try {
                                val result=transport.json("/api/connect/requests/$requestId")
                                if(result.optString("state")=="approved") {
                                    require(result.getString("computerId")==id && result.getString("certificateSha256")==pin) { "电脑身份发生变化" }
                                    val token=result.getString("token");require(token.length>=32) { "设备授权无效" }
                                    ui.post { if(current())runCatching {
                                        val old=computers.all().firstOrNull { it.id==id }
                                        require(old==null || old.pin==pin) { "电脑证书已变化，请先核对原连接" }
                                        val lan=if(target.mode=="lan")target.url else old?.let { if(it.mode=="lan")it.url else it.lanUrl } ?: ""
                                        val public=if(target.mode=="public")target.url else old?.let { if(it.mode=="public")it.url else it.publicUrl } ?: ""
                                        connectComputer(ComputerProfile(id,result.getString("computerName"),target.url,token,pin,target.mode,lan,public))
                                    }.onFailure { toast(it.message ?: "保存连接失败") } }
                                } else if(result.optString("state")=="denied")ui.post { if(current())label.text="电脑已拒绝本次配对" }
                                else ui.post { if(current())ui.postDelayed(this,1500) }
                            } catch(e:Exception) { failure(e) }
                        }
                    }
                }
                ui.post { if(current())pollPair.run() }
            } catch(e:Exception) { failure(e) }
        }
    }

    private fun toggleRecording() {
        if(recording!=null) { finishRecording(); return }
        if(checkSelfPermission(Manifest.permission.RECORD_AUDIO)!=PackageManager.PERMISSION_GRANTED) { requestPermissions(arrayOf(Manifest.permission.RECORD_AUDIO),1); return }
        hideKeyboard(); releasePlayback()
        runCatching { val value=VoiceRecorder(); recording=value; value.start { postResult { if(recording===value)finishRecording() } }; localError="" }.onFailure { recording=null; toast(it.message ?: "无法开始录音") }
        updateControls()
    }
    private fun finishRecording() {
        val value=recording ?: return
        recording=null; val audio=value.stop(); val selected=sessionId
        if(audio.size<9644 || value.error!=null) { toast(value.error ?: "录音太短，请再说一次"); updateControls(); return }
        voiceBusy=true; updateControls()
        work {
            val result=JSONObject(requestClient().bytes("/api/transcribe",audio,"audio/wav").toString(Charsets.UTF_8)).getString("text")
            postResult {
                voiceBusy=false
                if(selected==sessionId) { val prefix=input.text.toString(); input.setText(prefix+(if(prefix.isEmpty())"" else " ")+result); input.setSelection(input.text.length); localError="" }
                else { computers.putState("draft:$selected",result); toast("识别文字已保存到原对话草稿") }
                updateControls()
            }
        }
    }
    override fun onRequestPermissionsResult(requestCode:Int,permissions:Array<out String>,grantResults:IntArray) {
        super.onRequestPermissionsResult(requestCode,permissions,grantResults)
        if(requestCode==1 && grantResults.firstOrNull()==PackageManager.PERMISSION_GRANTED)toggleRecording() else toast("允许麦克风权限后才能录音")
    }
    private fun speak(id:String) {
        if(id.isEmpty())return
        val selected=sessionId
        releasePlayback(); val generation=playbackGeneration
        toast("正在准备朗读")
        work {
            val audio=requestClient().bytes("/api/speak",JSONObject().put("sessionId",selected).put("messageId",id).toString().toByteArray(Charsets.UTF_8))
            postResult {
                if(selected!=sessionId || generation!=playbackGeneration)return@postResult
                val path=File(cacheDir,"reply-$generation.wav").apply { writeBytes(audio) }
                playbackFile=path
                runCatching {
                    val playback=MediaPlayer()
                    player=playback
                    playback.apply {
                        setAudioAttributes(AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_MEDIA).setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build())
                        setDataSource(path.absolutePath)
                        setOnPreparedListener {
                            if(player===it && resumed && generation==playbackGeneration)it.start() else it.release()
                        }
                        setOnCompletionListener { if(player===it)releasePlayback() else { it.release(); path.delete() } }
                        setOnErrorListener { failed,_,_ ->
                            if(player===failed) { releasePlayback(); toast("朗读失败，请检查手表音量") } else failed.release()
                            true
                        }
                        prepareAsync()
                    }
                }.onFailure { releasePlayback(); toast("朗读失败，请检查手表音量") }
            }
        }
    }
    @Deprecated("Platform back navigation")
    override fun onBackPressed() { navigateBack() }
}
