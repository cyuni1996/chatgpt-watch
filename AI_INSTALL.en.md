# AI installation runbook

[中文](AI_INSTALL.md) · [Overview](README.en.md) · [Manual installation](docs/INSTALL.en.md)

## Copy this request to your AI

Use Codex on the target Windows computer, or another assistant with terminal access. A browser-only chat cannot operate your local machine.

```text
Please install https://github.com/cyuni1996/chatgpt-watch for me.
Read AI_INSTALL.en.md in the repository first and follow its procedure.
Prefer the signed Release APK matching the companion source version, and verify its SHA-256.
Check computer dependencies, connect my watch, install the app, start the companion and guide me through LAN pairing.
Preserve existing applications, pairing and drafts. Do not uninstall or clear data to resolve a signature conflict, and do not disable the firewall.
Verify by reading history, without sending test prompts or approving real desktop actions.
If I must unlock the watch, enable wireless debugging, enter its current debugging code or confirm the first connection, explain briefly at that step.
Finish with how to chat, how to start it next time, and what was actually verified.
```

The user must still unlock the watch, authorize wireless debugging and confirm the first connection. LAN chat connections require no code. The wireless debugging code is used for installation.

## Execution order

### 1. Inspect and choose the shortest route

Clone to a normal local directory. Check Python, Node, Codex CLI and ADB, reusing installed tools without assuming the maintainer's paths.

```powershell
git clone https://github.com/cyuni1996/chatgpt-watch.git
cd chatgpt-watch
python tools/setup_watch.py doctor --target companion --desktop
python tools/setup_watch.py doctor --target install
```

A nonzero `doctor` result means prerequisites are missing: read its JSON, resolve those items and retry. Doctor itself works without third-party Python packages. The companion requires Windows, Python 3.11+ and Node.js 20+; the model catalog uses `codex` on PATH. Installing a signed APK on an API 30+ watch only needs ADB: **no JDK, Gradle or full Android Studio is necessary**. Build from source only for development or when the release route is unavailable.

Obtain missing tools through official installers/package managers and respect the user's and host assistant's permissions. Do not silently install system services, startup entries or tunnels, or modify firewall rules.

### 2. Download and verify the signed APK

```powershell
python tools/setup_watch.py download
```

The downloader matches the checked-out source version to its GitHub Release, verifies SHA-256, and prints the APK path under `.local/downloads/`. If no matching release exists, build the source below or switch to a published Git tag and follow that tag's companion and watch setup instructions.

The release uses the default application ID `org.watchchat.app`. In-place updates require the same ID and signing key. If they differ, preserve the existing installation and data. The same source can keep a custom application ID through a local setting.

### 3. Install on the user's selected watch

Try `adb mdns services` for already paired devices. Ask for the watch's current debugging address/port only if discovery fails. If pairing is needed, have the user open the pairing screen and use `adb pair` with its current code. Do not scan arbitrary addresses or guess codes.

```powershell
adb connect WATCH_IP:DEBUG_PORT
python tools/setup_watch.py install --apk PATH_TO_VERIFIED_APK
```

Only authorized connected devices are accepted. With multiple devices, require `--serial WATCH_IP:DEBUG_PORT`. Use `--adb PATH_TO_ADB` if necessary. Installation uses `install -r` only, without an uninstall fallback.

### 4. Start and pair the application

```powershell
python tools/setup_watch.py deps
python tools/setup_watch.py start
python tools/setup_watch.py pair
```

- When run inside the current Codex chat, use its real `CODEX_THREAD_ID`; the launcher saves it automatically. Never use a sample ID as a real caller.
- If neither the variable nor saved local configuration exists, obtain an existing local Codex chat UUID and run `start --caller-thread-id REAL_CHAT_UUID`. Another AI must not invent a UUID to bypass this requirement.
- If the port is occupied, identify its owner. Use this project's stop script from the checkout that started the companion. Leave unrelated services and Codex desktop running.
- `pair` opens a three-minute LAN pairing window. For first-time pairing, scan for the computer on the watch, select it, then tap **确认配对** (Confirm pairing). The computer accepts the request and closes the window. To reconnect, select a saved computer, scan, or enter its address manually.
- If the user requests Internet access, follow the manual guide for their existing TCP tunnel.

### 5. Read-only verification and handoff

```powershell
python tools/setup_watch.py verify
```

The output contains history counts, not messages or tokens. Confirm the watch displays history and can open a user-selected chat. Do not send a test prompt or approve a live task without explicit authorization.

Report the installed version, actual connection mode, completed/incomplete checks, how to chat, how to run `Start Companion.cmd` after a reboot, and how to stop the companion. Computer, desktop and companion must remain running; locking is supported, sleep/shutdown is not. Daily communication does not require ADB.

## Source-build fallback

Requires JDK 17 or 21, Android SDK Platform 35, Build Tools 34.0.0, and Platform Tools. Set `JAVA_HOME` and `ANDROID_HOME` to the installed JDK and SDK.

```powershell
python tools/setup_watch.py doctor --target build
python tools/setup_watch.py build
python tools/setup_watch.py install
```

Use `build --mirror` to explicitly opt into the repository mirrors when necessary; keep TLS validation enabled. A locally built debug APK has a different signing identity from the published release. The default source release build remains unsigned; the publishing key is not included.
