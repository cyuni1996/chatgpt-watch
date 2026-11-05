package org.watchchat.app

import android.content.ContentProvider
import android.content.ContentValues
import android.database.Cursor
import android.net.Uri
import android.os.Binder
import android.os.ParcelFileDescriptor
import java.io.File

/** Authorized ADB provisioning for release builds. No credentials in intents or URIs. */
class PairingProvider : ContentProvider() {
    override fun onCreate()=true
    override fun openFile(uri: Uri, mode: String): ParcelFileDescriptor {
        val uid=Binder.getCallingUid()
        if(uid!=2000 && uid!=0)throw SecurityException("Only an authorized ADB shell can provision pairing")
        require(uri.path=="/pairing" && mode=="w") { "Unsupported pairing operation" }
        return ParcelFileDescriptor.open(File(requireNotNull(context).filesDir,"pairing.json"),
            ParcelFileDescriptor.MODE_CREATE or ParcelFileDescriptor.MODE_TRUNCATE or ParcelFileDescriptor.MODE_WRITE_ONLY)
    }
    override fun getType(uri: Uri)="application/json"
    override fun query(uri: Uri, projection: Array<out String>?, selection: String?, selectionArgs: Array<out String>?, sortOrder: String?): Cursor?=throw UnsupportedOperationException()
    override fun insert(uri: Uri, values: ContentValues?): Uri?=throw UnsupportedOperationException()
    override fun delete(uri: Uri, selection: String?, selectionArgs: Array<out String>?): Int=throw UnsupportedOperationException()
    override fun update(uri: Uri, values: ContentValues?, selection: String?, selectionArgs: Array<out String>?): Int=throw UnsupportedOperationException()
}
