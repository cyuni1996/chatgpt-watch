# AI installation runbook

[中文](AI_INSTALL.md) · [Overview](README.en.md) · [Manual installation](docs/INSTALL.en.md)

## Copy this request to your AI

Use Codex on the target Windows computer, or another assistant with terminal access. A browser-only chat cannot operate your local machine.

```text
Please install https://github.com/cyuni1996/chatgpt-watch for me.
Read AI_INSTALL.en.md in the repository first and follow its procedure.
Prefer the signed APK from the project's GitHub Release, verify SHA-256, and avoid installing an unnecessary Android build toolchain.
Check computer dependencies, connect my watch, install the app, start the companion and guide me through LAN pairing.
Preserve existing applications, pairing and drafts. Do not uninstall or clear data to resolve a signature conflict, and do not disable the firewall.
Verify by reading history, without sending test prompts or approving real desktop actions.
If I must unlock the watch, enable wireless debugging, enter its current pairing code or compare connection codes, explain briefly at that step.
Finish with how to chat, how to start it next time, and what was actually verified.
```

The user must still unlock the watch, authorize wireless debugging and compare pairing codes. Android debugging codes and this application's connection codes are different. Never post them in public issues.

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
python tools/setup_watch.py download --tag v0.13.0
```

The downloader fetches `chatgpt-watch-0.13.0.apk` and `SHA256SUMS` from this repository's release, matches the exact filename and verifies its digest. Files are stored in ignored `.local/downloads/v0.13.0/`. Stop on a mismatch; do not bypass verification.

The release uses its own public-build signing identity and application ID `org.watchchat.app`, separate from private builds with another ID. An existing app with the same ID but a different signature cannot be updated in place. **Report the conflict and preserve the installation; never automatically uninstall or clear data.**

### 3. Install on the user's selected watch

Try `adb mdns services` for already paired devices. Ask for the watch's current debugging address/port only if discovery fails. If pairing is needed, have the user open the pairing screen and use `adb pair` with its current code. Do not scan arbitrary addresses or guess codes.

```powershell
adb connect WATCH_IP:DEBUG_PORT
python tools/setup_watch.py install --apk .local/downloads/v0.13.0/chatgpt-watch-0.13.0.apk
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
- If another service owns the port, identify and report it. Do not stop a private build, unrelated project or Codex desktop to take the port.
- `pair` opens a three-minute window and waits. Have the user select **设置 → 电脑连接 → 局域网扫描** on the watch, select the computer, compare both codes, then enter `y` on the computer. Never automatically approve an unchecked code.
- Do not deploy a public endpoint unless requested and a domain/tunnel is available.

### 5. Read-only verification and handoff

```powershell
python tools/setup_watch.py verify
```

The output contains history counts, not messages or tokens. Confirm the watch displays history and can open a user-selected chat. Do not send a test prompt or approve a live task without explicit authorization.

Report the installed version, actual connection mode, completed/incomplete checks, how to chat, how to run `Start Companion.cmd` after a reboot, and how to stop the companion. Computer, desktop and companion must remain running; locking is supported, sleep/shutdown is not. Daily communication does not require ADB.

## Source-build fallback

Requires JDK 17/21, Android SDK Platform 35 and Platform Tools. Set `ANDROID_HOME`/`ANDROID_SDK_ROOT` to the actual SDK.

```powershell
python tools/setup_watch.py doctor --target build
python tools/setup_watch.py build
python tools/setup_watch.py install
```

Use `build --mirror` to explicitly opt into the repository mirrors when necessary; keep TLS validation enabled. A locally built debug APK has a different signing identity from the published release. The default source release build remains unsigned; the publishing key is not included.
