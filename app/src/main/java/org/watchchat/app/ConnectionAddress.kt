package org.watchchat.app

import java.net.URI
import java.security.MessageDigest

object ConnectionAddress {
    /** Pick an address on the watch's Wi-Fi subnet, never a PC's virtual adapter. */
    fun lanAddress(addresses:List<String>,subnets:List<Pair<String,Int>>):String? {
        fun ipv4(value:String):Long? {
            val parts=value.split('.');if(parts.size!=4)return null
            var bits=0L
            for(part in parts) { val n=part.toIntOrNull() ?: return null;if(n !in 0..255)return null;bits=(bits shl 8) or n.toLong() }
            return bits
        }
        return addresses.firstOrNull { candidate ->
            val bits=ipv4(candidate)
            bits!=null && subnets.any { (local,prefix) ->
                val own=ipv4(local);val mask=if(prefix in 1..32)(0xffffffffL shl (32-prefix)) and 0xffffffffL else 0L
                own!=null && mask!=0L && (bits and mask)==(own and mask)
            }
        }
    }
    fun publicUrl(value:String):String {
        val raw=if(value.trim().contains("://"))value.trim() else "https://"+value.trim()
        val u=URI(raw);val host=u.host?.lowercase() ?: error("请输入有效的公网域名")
        require(u.scheme.lowercase()=="https" && u.rawUserInfo==null && u.rawQuery==null && u.rawFragment==null && u.path in listOf("","/") && u.port in listOf(-1,443)) { "请输入HTTPS域名，不包含路径或端口" }
        require(host.contains('.') && !host.matches(Regex("[0-9.]+")) && !host.contains(':') && !host.endsWith(".local") && !host.endsWith(".lan") && !host.endsWith(".internal")) { "公网模式请使用固定域名" }
        return "https://$host"
    }
    fun hash(value:String)=MessageDigest.getInstance("SHA-256").digest(value.toByteArray(Charsets.UTF_8)).joinToString("") { "%02x".format(it) }
    fun code(id:String,pin:String,mode:String,url:String,requestId:String,claimHash:String):String =
        hash(listOf("watch-pair-v1",id,pin,mode,url,requestId,claimHash).joinToString("\n")).take(12).uppercase().chunked(4).joinToString("-")
}
