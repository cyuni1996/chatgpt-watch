package org.watchchat.app

import android.os.Looper
import android.os.SystemClock
import android.view.MotionEvent
import android.view.View
import android.view.ViewGroup
import android.view.WindowManager
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.Shadows.shadowOf
import org.robolectric.android.controller.ActivityController
import org.robolectric.annotation.Config
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import org.json.JSONObject
import org.json.JSONArray

@RunWith(RobolectricTestRunner::class)
@Config(sdk=[30])
class MainActivityTest {
    private lateinit var controller: ActivityController<MainActivity>
    private lateinit var activity: MainActivity
    private fun call(name: String) { MainActivity::class.java.getDeclaredMethod(name).apply { isAccessible=true }.invoke(activity) }
    private fun value(name: String): Any?=MainActivity::class.java.getDeclaredField(name).apply { isAccessible=true }.get(activity)
    private fun set(name: String,value: Any) { MainActivity::class.java.getDeclaredField(name).apply { isAccessible=true }.set(activity,value) }

    @Before fun start() {
        android.provider.Settings.Global.putFloat(RuntimeEnvironment.getApplication().contentResolver,android.provider.Settings.Global.ANIMATOR_DURATION_SCALE,0f)
        RuntimeEnvironment.getApplication().getSharedPreferences("connection",0).edit().clear().commit()
        controller=Robolectric.buildActivity(MainActivity::class.java).setup().visible()
        activity=controller.get()
        shadowOf(Looper.getMainLooper()).idle()
        call("closeOverlay")
        layout()
    }
    @After fun stop() { controller.pause().stop().destroy() }
    private fun layout() {
        val decor=activity.window.decorView
        decor.measure(View.MeasureSpec.makeMeasureSpec(500,View.MeasureSpec.EXACTLY),View.MeasureSpec.makeMeasureSpec(500,View.MeasureSpec.EXACTLY))
        decor.layout(0,0,500,500)
    }
    private fun swipe(left: Boolean, vertical: Boolean=false) {
        layout()
        val start=SystemClock.uptimeMillis()
        val x=if(left)380f else 100f
        val dx=if(left)-240f else 240f
        listOf(MotionEvent.ACTION_DOWN,MotionEvent.ACTION_MOVE,MotionEvent.ACTION_UP).forEachIndexed { i,action ->
            val event=MotionEvent.obtain(start,start+i*100L,action,x+dx*i/2,210f+if(vertical)i*150 else 0,0)
            activity.dispatchTouchEvent(event); event.recycle()
        }
    }

    @Test fun leftThenRightSwipeReturnOnePageAndRootSwipeExits() {
        call("settingsPage"); val settings=value("overlay")
        call("inputHelp"); assertEquals("input-help",value("mode"))
        swipe(left=true)
        assertEquals("settings",value("mode")); assertSame(settings,value("overlay"))
        assertFalse(activity.isFinishing)
        swipe(left=false)
        assertEquals("chat",value("mode")); assertFalse(activity.isFinishing)
        swipe(left=true)
        assertTrue(activity.isFinishing)
    }

    @Test fun backKeyAndHeaderUseSameStackAndPageRefreshDoesNotDuplicateIt() {
        call("settingsPage"); call("settingsPage"); call("inputHelp")
        activity.onBackPressed()
        assertEquals("settings",value("mode"))
        val panel=value("overlay") as ViewGroup
        fun find(view: View): View? {
            if(view.contentDescription=="返回上一页")return view
            if(view is ViewGroup)for(i in 0 until view.childCount)find(view.getChildAt(i))?.let { return it }
            return null
        }
        assertTrue(find(panel)!!.performClick())
        assertEquals("chat",value("mode")); assertFalse(activity.isFinishing)
        activity.onBackPressed(); assertTrue(activity.isFinishing)
    }

    @Test fun mostlyVerticalDragDoesNotNavigate() {
        call("settingsPage"); call("inputHelp")
        swipe(left=true,vertical=true)
        assertEquals("input-help",value("mode")); assertFalse(activity.isFinishing)
    }

    @Test fun lateWorkerResultAfterPauseAndResumeCannotTouchUiOrWakeScreen() {
        val entered=CountDownLatch(1); val release=CountDownLatch(1); val posted=CountDownLatch(1)
        var called=false
        val job: () -> Unit = {
            entered.countDown()
            while(release.count>0)try { release.await() } catch(_:InterruptedException) {}
            val callback: () -> Unit = { called=true; set("voiceBusy",true); call("updateControls") }
            MainActivity::class.java.getDeclaredMethod("postResult",kotlin.jvm.functions.Function0::class.java)
                .apply { isAccessible=true }.invoke(activity,callback)
            posted.countDown()
        }
        MainActivity::class.java.getDeclaredMethod("work",kotlin.jvm.functions.Function0::class.java)
            .apply { isAccessible=true }.invoke(activity,job)
        assertTrue(entered.await(2,TimeUnit.SECONDS))
        controller.pause().stop().start().resume().visible()
        release.countDown(); assertTrue(posted.await(2,TimeUnit.SECONDS))
        shadowOf(Looper.getMainLooper()).idle()
        assertFalse(called)
        assertEquals(0,activity.window.attributes.flags and WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
    }

    @Test fun computerSwitchRestoresItsDraftAndRejectsTheOldComputersLateResult() {
        val store=ComputerProfiles(activity.getSharedPreferences("connection",0))
        val a=ComputerProfile("pc-a","A","https://a.invalid","token-a","a".repeat(64))
        val b=ComputerProfile("pc-b","B","https://b.invalid","token-b","b".repeat(64))
        store.save(b);store.putState("sessionId","same-id");store.putState("draft:same-id","B draft")
        store.save(a);store.putState("sessionId","same-id")
        set("sessionId","same-id")
        (value("input") as android.widget.EditText).setText("A draft")
        val entered=CountDownLatch(1);val release=CountDownLatch(1);val posted=CountDownLatch(1)
        val oldJob: () -> Unit = {
            entered.countDown()
            while(release.count>0)try { release.await() } catch(_:InterruptedException) {}
            val callback: () -> Unit = { (value("input") as android.widget.EditText).setText("old computer result") }
            MainActivity::class.java.getDeclaredMethod("postResult",kotlin.jvm.functions.Function0::class.java)
                .apply { isAccessible=true }.invoke(activity,callback)
            posted.countDown()
        }
        MainActivity::class.java.getDeclaredMethod("work",kotlin.jvm.functions.Function0::class.java)
            .apply { isAccessible=true }.invoke(activity,oldJob)
        assertTrue(entered.await(2,TimeUnit.SECONDS))
        // Prevent real I/O; resume the UI after the switch so generation isolation is tested.
        set("resumed",false)
        MainActivity::class.java.getDeclaredMethod("connectComputer",ComputerProfile::class.java)
            .apply { isAccessible=true }.invoke(activity,b)
        set("resumed",true);release.countDown();assertTrue(posted.await(2,TimeUnit.SECONDS))
        shadowOf(Looper.getMainLooper()).idle()
        assertEquals("B draft",(value("input") as android.widget.EditText).text.toString())
        assertEquals("A draft",prefsState(store,a.id,"draft:same-id"))
        assertEquals("B draft",store.getState("draft:same-id"))
    }
    private fun prefsState(store: ComputerProfiles,id: String,key: String): String?=
        activity.getSharedPreferences("connection",0).getString(store.stateKey(key,id),null)

    @Test fun sendPositionTogglesToStopWithoutAnExtraControlRow() {
        set("client",BridgeClient("https://watch.invalid","test","0".repeat(64)))
        val input=value("input") as android.widget.EditText
        input.setText("next question")
        set("state",JSONObject().put("connected",true).put("busy",false))
        call("updateControls")
        val button=value("send") as GlyphButton
        assertEquals("send",button.glyph);assertTrue(button.isEnabled)
        set("state",JSONObject().put("connected",true).put("busy",true).put("canInterrupt",true))
        call("updateControls")
        assertEquals("stop",button.glyph);assertEquals("停止本次回复",button.contentDescription)
        assertTrue(button.isEnabled)
        fun hasSeparateStop(view: View): Boolean {
            if(view is android.widget.TextView && view.text.toString()=="停止回复")return true
            return view is ViewGroup && (0 until view.childCount).any { hasSeparateStop(view.getChildAt(it)) }
        }
        assertFalse(hasSeparateStop(activity.window.decorView))
        set("state",JSONObject().put("connected",true).put("busy",false));call("updateControls")
        assertEquals("send",button.glyph);assertEquals("next question",input.text.toString())
    }

    @Test fun headerPullDownOpensUsageAndChatBodyDragKeepsScrolling() {
        fun down(y: Float) {
            layout()
            val time=SystemClock.uptimeMillis()
            listOf(MotionEvent.ACTION_DOWN,MotionEvent.ACTION_MOVE,MotionEvent.ACTION_UP).forEachIndexed { i,action ->
                val event=MotionEvent.obtain(time,time+i*100L,action,250f,y+i*80f,0)
                activity.dispatchTouchEvent(event);event.recycle()
            }
        }
        down(40f);assertEquals("usage",value("mode"))
        activity.onBackPressed();assertEquals("chat",value("mode"))
        val header=android.graphics.Rect();(value("headerTitles") as View).getGlobalVisibleRect(header)
        down((header.bottom-4).toFloat());assertEquals("usage",value("mode"))
        activity.onBackPressed();assertEquals("chat",value("mode"))
        down(210f);assertEquals("chat",value("mode"));assertFalse(activity.isFinishing)
    }

    @Test fun pendingChoiceAutomaticallyOpensOneModalAndHeaderCanReopenIt() {
        set("client",BridgeClient("https://watch.invalid","test","0".repeat(64)))
        val item=JSONObject().put("token","a".repeat(64)).put("title","请选择回复")
            .put("questions",JSONArray()).put("actions",JSONArray())
        set("state",JSONObject().put("connected",true).put("approvals",JSONArray().put(item)))
        call("updateControls");shadowOf(Looper.getMainLooper()).idle()
        val dialog=value("approvalDialog") as android.app.Dialog
        assertTrue(dialog.isShowing);assertEquals("approval",value("mode"))
        dialog.onBackPressed();shadowOf(Looper.getMainLooper()).idle()
        assertNull(value("approvalDialog"));assertEquals("chat",value("mode"))
        call("updateControls");shadowOf(Looper.getMainLooper()).idle()
        assertNull(value("approvalDialog"))
        assertTrue((value("headerTitles") as View).performClick())
        assertEquals("context",value("mode"));assertNull(value("approvalDialog"))
        fun all(v:View):List<View> = listOf(v)+(if(v is ViewGroup)(0 until v.childCount).flatMap { all(v.getChildAt(it)) } else emptyList())
        all(value("overlay") as View).filterIsInstance<android.widget.TextView>().first { it.text.toString()=="待确认操作" }.performClick()
        assertTrue((value("approvalDialog") as android.app.Dialog).isShowing)
    }
    @Test fun newChatFirstOpensProjectPickerWithoutSwitchingTheCurrentDraft() {
        set("sessionId","original-draft")
        (value("input") as android.widget.EditText).setText("keep my draft")
        call("newChat")
        assertEquals("projects",value("mode"))
        assertEquals("original-draft",value("sessionId"))
        assertEquals("keep my draft",(value("input") as android.widget.EditText).text.toString())
    }

    @Test fun projectPickerResumesAfterCancelledLoadWithoutDuplicatingNavigation() {
        call("settingsPage");call("newChat")
        val depth=(value("panelHistory") as java.util.ArrayDeque<*>).size
        controller.pause().stop().start().resume().visible()
        assertEquals("projects",value("mode"))
        assertEquals(depth,(value("panelHistory") as java.util.ArrayDeque<*>).size)
        assertTrue(value("projectPickerCreatesChat") as Boolean)
    }

    @Test fun nullThreadIdDraftKeepsItsProjectPickerAndCompactContextRow() {
        set("state",JSONObject().put("threadId",JSONObject.NULL).put("projectName","Sample Watch").put("connected",true))
        call("updateControls")
        val chip=value("projectText") as android.widget.TextView
        assertEquals("Sample Watch ⌄",chip.text.toString())
        assertNull(chip.parent);assertTrue((value("modelText") as View).isAttachedToWindow)
        (value("headerTitles") as View).performClick()
        assertEquals("context",value("mode"))
        (value("projectText") as View).performClick()
        assertEquals("projects",value("mode"))
    }

    @Test fun drawerGroupsProjectsDisplaysStatesAndExpandsEachProjectIndependently() {
        call("openDrawer")
        set("drawerLoading",false)
        set("drawerProjects",JSONArray().put(JSONObject().put("id","p").put("name","Sample Watch")))
        val items=JSONArray()
        listOf("running" to "运行中","waiting" to "等你回复","unread" to "有新回复","idle" to "空闲").forEachIndexed { i,pair ->
            items.put(JSONObject().put("threadId","t$i").put("title","chat$i").put("projectId","p").put("projectName","Sample Watch").put("status",pair.first).put("statusLabel",pair.second))
        }
        items.put(JSONObject().put("threadId","other").put("title","other chat").put("projectId",JSONObject.NULL).put("statusLabel","空闲"))
        set("drawerItems",items);call("drawDrawerRows")
        fun descendants(view:View):List<View> = listOf(view)+(if(view is ViewGroup)(0 until view.childCount).flatMap { descendants(view.getChildAt(it)) } else emptyList())
        fun views()=descendants(value("drawerRows") as View)
        fun texts()=views().filterIsInstance<android.widget.TextView>().map { it.text.toString() }
        assertTrue(views().any { it.contentDescription=="项目分组：Sample Watch" })
        assertTrue(views().any { it.contentDescription=="项目分组：其他聊天" })
        assertTrue(texts().containsAll(listOf("运行中","等你回复","有新回复")))
        assertFalse(texts().contains("chat3"))
        views().filterIsInstance<android.widget.TextView>().first { it.text.toString().startsWith("展开 Sample Watch") }.performClick()
        assertTrue(texts().contains("chat3"))
        assertTrue(texts().contains("other chat"))
    }

    @Test @Config(qualifiers="w240dp-h240dp-round-mdpi")
    fun realHeaderBoundsAndPanelsUseTheFullDisplayWithSafeButtons() {
        fun measured() {
            val decor=activity.window.decorView
            decor.measure(View.MeasureSpec.makeMeasureSpec(240,View.MeasureSpec.EXACTLY),View.MeasureSpec.makeMeasureSpec(240,View.MeasureSpec.EXACTLY));decor.layout(0,0,240,240)
        }
        fun all(view:View):List<View> = listOf(view)+(if(view is ViewGroup)(0 until view.childCount).flatMap { all(view.getChildAt(it)) } else emptyList())
        fun check(label:String) {
            val view=all(activity.window.decorView).first { it.contentDescription==label }
            val pos=IntArray(2);view.getLocationOnScreen(pos)
            val cx=pos[0]+view.width/2f;val cy=pos[1]+view.height/2f
            assertTrue("$label circle",kotlin.math.sqrt((cx-120)*(cx-120)+(cy-120)*(cy-120))+view.width/2f<=117)
            assertTrue(view.width>=36);assertTrue(view.height>=36)
        }
        measured();check("打开历史对话");check("设置")
        call("openDrawer");measured()
        val overlay=value("overlay") as ViewGroup
        assertEquals(240,overlay.width);assertEquals(240,overlay.height)
        assertEquals(240,overlay.getChildAt(0).width)
        check("关闭历史对话");check("新建对话");check("搜索聊天")
        call("settingsPage");measured();check("返回上一页")
    }

    @Test fun appearanceChangesPersistWithoutChangingComputerSessionOrDraft() {
        val prefs=activity.getSharedPreferences("connection",0)
        prefs.edit().putString("activeComputer","keep-computer").commit()
        set("sessionId","keep-chat")
        val input=value("input") as android.widget.EditText;input.setText("keep this draft")
        call("appearancePage")
        fun all(view:View):List<View> = listOf(view)+(if(view is ViewGroup)(0 until view.childCount).flatMap { all(view.getChildAt(it)) } else emptyList())
        val toggle=all(value("overlay") as View).filterIsInstance<android.widget.TextView>().first { it.text.toString().startsWith("背景：") }
        toggle.performClick()
        assertTrue(prefs.getBoolean("ui.quietBackground",false))
        assertEquals("keep-chat",value("sessionId"));assertEquals("keep this draft",input.text.toString())
        assertEquals("keep-computer",prefs.getString("activeComputer",null))
        call("settingsPage");call("appearancePage")
        assertTrue(all(value("overlay") as View).filterIsInstance<android.widget.TextView>().any { it.text.toString()=="背景：纯净阅读" })
    }

    @Test fun drawerSearchOnlyUsesExtraRowWhenExpandedAndClosingClearsFilter() {
        call("openDrawer")
        val field=value("search") as android.widget.EditText
        assertEquals(View.GONE,field.visibility)
        fun all(view:View):List<View> = listOf(view)+(if(view is ViewGroup)(0 until view.childCount).flatMap { all(view.getChildAt(it)) } else emptyList())
        val button=all(value("overlay") as View).first { it.contentDescription=="搜索聊天" }
        button.performClick();assertEquals(View.VISIBLE,field.visibility)
        field.setText("test filter")
        button.performClick();assertEquals(View.GONE,field.visibility)
        assertEquals("",value("drawerQuery"))
    }

    @Test @Config(qualifiers="w240dp-h240dp-round-mdpi")
    fun compactChatGivesSpaceBackAndProjectModelRemainReachable() {
        val decor=activity.window.decorView
        decor.measure(View.MeasureSpec.makeMeasureSpec(240,View.MeasureSpec.EXACTLY),View.MeasureSpec.makeMeasureSpec(240,View.MeasureSpec.EXACTLY));decor.layout(0,0,240,240)
        val messages=value("chatScroll") as View
        assertEquals(101,messages.height)
        assertTrue((value("modelText") as View).isAttachedToWindow)
        assertNull((value("projectText") as View).parent)
        val field=value("input") as android.widget.EditText;field.setText("keep my draft")
        (value("headerTitles") as View).performClick();assertEquals("context",value("mode"))
        assertTrue((value("modelText") as View).isAttachedToWindow)
        assertTrue((value("projectText") as View).isAttachedToWindow)
        (value("modelText") as View).performClick();assertEquals("models",value("mode"))
        activity.onBackPressed();assertEquals("context",value("mode"))
        activity.onBackPressed();assertEquals("chat",value("mode"))
        assertEquals("keep my draft",field.text.toString())
    }

    @Test fun chatHasNoDarkScrollFadeAndKeepsTheExpandedViewport() {
        assertFalse((value("chatScroll") as android.widget.ScrollView).isVerticalFadingEdgeEnabled)
    }

    @Test fun settingsAndNestedPagesNeverDrawBlackFadingEdges() {
        fun all(view:View):List<View> = listOf(view)+(if(view is ViewGroup)(0 until view.childCount).flatMap { all(view.getChildAt(it)) } else emptyList())
        for(page in listOf("settingsPage","appearancePage","computersPage","inputHelp","openDrawer")) {
            call(page)
            val scrolls=all(value("overlay") as View).filterIsInstance<android.widget.ScrollView>()
            assertTrue("$page must exercise a scrolling panel",scrolls.isNotEmpty())
            for(scroll in scrolls) {
                assertFalse("$page bottom stripe",scroll.isVerticalFadingEdgeEnabled)
                assertFalse("$page side stripe",scroll.isHorizontalFadingEdgeEnabled)
                assertEquals(View.OVER_SCROLL_NEVER,scroll.overScrollMode)
            }
        }
    }

    @Test @Config(qualifiers="w240dp-h240dp-round-mdpi")
    fun panelViewportReachesTheScreenBottomButKeepsFixedActionsSeparate() {
        fun measure() {
            val decor=activity.window.decorView
            decor.measure(View.MeasureSpec.makeMeasureSpec(240,View.MeasureSpec.EXACTLY),View.MeasureSpec.makeMeasureSpec(240,View.MeasureSpec.EXACTLY));decor.layout(0,0,240,240)
        }
        call("settingsPage");measure()
        var page=(value("overlay") as ViewGroup).getChildAt(0) as ViewGroup
        val scroll=page.getChildAt(page.childCount-1) as android.widget.ScrollView
        assertEquals("No rectangular cut above the circular screen edge",page.height,scroll.bottom)
        assertEquals(0,page.paddingBottom)
        assertTrue(scroll.paddingBottom>=48)
        call("drawModels");measure()
        page=(value("overlay") as ViewGroup).getChildAt(0) as ViewGroup
        val save=page.getChildAt(page.childCount-1)
        val modelScroll=page.getChildAt(page.childCount-2) as android.widget.ScrollView
        assertTrue("Scrolling models must not cover Save",modelScroll.bottom<=save.top)
        assertTrue(save.bottom<=page.height-page.paddingBottom)
    }

}
