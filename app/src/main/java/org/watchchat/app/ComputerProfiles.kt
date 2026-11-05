package org.watchchat.app

import android.content.SharedPreferences
import org.json.JSONArray
import org.json.JSONObject
import java.util.UUID

data class ComputerProfile(val id: String, val name: String, val url: String, val token: String, val pin: String,
    val mode: String="lan", val lanUrl: String=if(mode=="lan")url else "", val publicUrl: String=if(mode=="public")url else "") {
    override fun toString()="ComputerProfile($id, $name)"
    fun json()=JSONObject().put("id",id).put("name",name).put("url",url).put("token",token).put("pin",pin)
        .put("mode",mode).put("lanUrl",if(mode=="lan")url else lanUrl).put("publicUrl",if(mode=="public")url else publicUrl)
    fun using(nextMode:String):ComputerProfile {
        require(nextMode in listOf("lan","public")) { "连接模式无效" }
        val endpoint=if(nextMode=="lan") { if(mode=="lan")url else lanUrl } else { if(mode=="public")url else publicUrl }
        require(endpoint.isNotEmpty()) { "请先配置此模式的地址" }
        return copy(url=endpoint,mode=nextMode,lanUrl=if(mode=="lan")url else lanUrl,publicUrl=if(mode=="public")url else publicUrl)
    }
}

/** Connection credentials and all mutable chat state are scoped to a computer. */
class ComputerProfiles(private val prefs: SharedPreferences) {
    fun all(): List<ComputerProfile> {
        val data=JSONArray(prefs.getString("computers","[]"))
        return (0 until data.length()).map {
            val item=data.getJSONObject(it)
            val mode=item.optString("mode","lan");val url=item.getString("url")
            ComputerProfile(item.getString("id"),item.getString("name"),url,item.getString("token"),item.getString("pin"),
                mode,item.optString("lanUrl",if(mode=="lan")url else ""),item.optString("publicUrl",if(mode=="public")url else ""))
        }
    }
    fun activeId(): String=prefs.getString("activeComputer","") ?: ""
    fun active(): ComputerProfile?=all().firstOrNull { it.id==activeId() }
    fun stateKey(key: String, id: String=activeId())="computer:$id:$key"
    fun getState(key: String): String=prefs.getString(stateKey(key),"") ?: ""
    fun putState(key: String, value: String) { prefs.edit().putString(stateKey(key),value).apply() }

    fun migrateLegacy() {
        if(all().isNotEmpty())return
        val url=prefs.getString("url","") ?: ""
        val pin=prefs.getString("pin","") ?: ""
        val token=prefs.getString("token","") ?: ""
        if(url.isBlank() || pin.isBlank() || token.isBlank())return
        val id=UUID.nameUUIDFromBytes((url+"|"+pin).toByteArray(Charsets.UTF_8)).toString()
        val profile=ComputerProfile(id,"原来的电脑",url,token,pin)
        val editor=prefs.edit()
        for((key,value) in prefs.all) {
            if(value is String && (key=="sessionId" || key=="draft" || key.startsWith("draft:") || key.startsWith("pendingText:") || key.startsWith("pendingId:")))
                editor.putString(stateKey(key,id),value)
        }
        val session=prefs.getString("sessionId","") ?: ""
        val oldDraft=prefs.getString("draft","") ?: ""
        if(oldDraft.isNotEmpty() && !prefs.contains("draft:$session"))editor.putString(stateKey("draft:$session",id),oldDraft)
        // Preserve unknown and legacy fields for rollback; migrate atomically, exactly once.
        check(editor.putString("computers",JSONArray().put(profile.json()).toString()).putString("activeComputer",id).commit())
    }

    fun save(profile: ComputerProfile, activate: Boolean=true) {
        require(profile.id.matches(Regex("[A-Za-z0-9_-]{1,100}"))) { "电脑编号无效" }
        require(profile.name.isNotBlank() && profile.name.length<=40) { "电脑名称需为1到40个字符" }
        require(profile.mode in listOf("lan","public")) { "连接模式无效" }
        val values=all().toMutableList()
        val index=values.indexOfFirst { it.id==profile.id }
        if(index<0)values.add(profile) else values[index]=profile
        val editor=prefs.edit().putString("computers",JSONArray().apply { values.forEach { put(it.json()) } }.toString())
        if(activate)editor.putString("activeComputer",profile.id)
        check(editor.commit()) { "电脑连接保存失败" }
    }
    fun activate(id: String) {
        require(all().any { it.id==id }) { "电脑连接不存在" }
        check(prefs.edit().putString("activeComputer",id).commit()) { "切换电脑失败" }
    }
}
