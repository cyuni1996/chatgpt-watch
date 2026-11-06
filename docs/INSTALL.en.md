# Installation, connections and maintenance

[中文](INSTALL.zh-CN.md) · [Project overview](../README.en.md)

**Recommended: use the [AI installation runbook](../AI_INSTALL.en.md).** The prebuilt release is already signed; installing it requires ADB, not an Android source-build toolchain. Full manual/developer instructions remain below.

These instructions cover a complete first installation. Verify LAN history reading before setting up Internet access. The companion primarily supports Windows.

## Preflight

```powershell
python --version
node --version
codex --version
adb version
```

Use Python 3.11+, Node.js 20+, signed-in Codex desktop and Android Platform Tools (ADB). The model catalog also requires `codex` on PATH. The prebuilt APK does not require JDK or Android Studio. Activate your virtual environment first if applicable.

## Download and install

Choose a [GitHub release](https://github.com/cyuni1996/chatgpt-watch/releases), then clone the matching Git tag in PowerShell. The example uses `v0.13.9`.

```powershell
git clone --branch v0.13.9 https://github.com/cyuni1996/chatgpt-watch.git
cd chatgpt-watch
python tools/setup_watch.py deps
python tools/setup_watch.py download
```

The downloader verifies the release SHA-256 and prints the APK path. Follow the setup instructions in the checked-out tag. For a development checkout without a matching release, see [source build](#source-build). Enable wireless debugging on the watch and use its current addresses. Pairing and debugging ports usually differ.

```powershell
adb pair WATCH_IP:PAIRING_PORT
adb connect WATCH_IP:DEBUG_PORT
python tools/setup_watch.py install --apk .local/downloads/v0.13.9/chatgpt-watch-0.13.9.apk
```

Skip `adb pair` for an already paired watch. Add `--serial` for multiple devices and `--adb` when ADB is not on PATH. The public app ID is `org.watchchat.app`; in-place updates need the same ID and signing key. Never automatically uninstall or clear data after an installation failure.

## Caller context and lifecycle

Desktop tools require a real existing local caller chat:

```powershell
python tools/computer_runtime.py --caller-thread-id YOUR_EXISTING_CHAT_UUID --name "My PC"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools/start-companion.ps1
```

Starting from a Codex project context can automatically save `CODEX_THREAD_ID` when that environment variable is provided. UUID validation checks syntax only; it does not prove the chat exists or is accessible. An invalid caller can prevent history reading or chat creation.

Each computer uses an independent identity in `.local/computers/<machine-key>/`. Copy source code, not `.local`, when setting up another computer, and pair it separately. The default computer name comes from the OS hostname; use `--name` to choose a non-personal alias. A successful process launch does not prove desktop protocol connectivity; verify actual history on the watch.

Stop only this project's companion with:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools/stop-companion.ps1
```

Start once per running session, then restart after a computer reboot. This release does not install a tray application, scheduled task, or system service. Previously submitted Codex work can continue after the companion stops; use the chat's Stop action to interrupt a response.

## LAN connection

1. Connect both devices to a mutually reachable network; avoid guest/client isolation.
2. Allow this Python process's TCP 8766 and mDNS UDP 5353 only on trusted Windows network profiles. Do not disable the whole firewall.
3. Run **Start Companion.cmd**. For first-time pairing, press **L** in the same window to open a three-minute pairing window.
4. On the watch open **设置 → 电脑连接 → 局域网扫描** (Settings → Computer connection → LAN scan) and select the computer.
5. Check the computer name and address, then tap **确认配对** (Confirm pairing) on the watch. The computer accepts automatically. The window closes after one pairing or three minutes.
6. **局域网扫描** (LAN scan) lists both saved and newly discovered computers. Select the one you want. If its address is unchanged, you can also select the saved computer directly from **电脑连接** (Computer connection).

Daily communication does not require ADB. Wireless debugging is for installing and updating the app, and uses a separate port from the companion. First-time code-free pairing requires Wi-Fi, IPv4 and mDNS discovery. A previously paired computer can also reconnect by IP and port.

## Internet connection

LAN and Internet connections share the same companion service. Run **Start Companion.cmd** to see each adapter's local IP and the TCP port (default `8766`). Map your external TCP port to an adapter IP reachable from your tunnel and pass through HTTPS so the watch can verify the companion's certificate.

1. Press **P** in the same CMD window to generate a one-time Internet pairing code. The code expires after three minutes.
2. On the watch, open **设置 → 电脑连接 → 外网连接** (Settings → Computer connection → Internet connection). Enter the full HTTPS address (for example, `https://203.0.113.5:24876`) and the code. The watch can pair for the first time over the Internet.
3. After pairing, reconnect from the saved computer list. Back on the LAN, scan and select the same computer. The app saves the two addresses separately and uses the same conversations and drafts.

## Device authorization

```powershell
python tools/manage_connections.py devices
python tools/manage_connections.py revoke --device-id DEVICE_ID_FROM_LIST
```

Newly paired watches receive independent tokens whose hashes are stored server-side. Legacy shared-token compatibility is separate: revoking one newly paired device does not revoke every old credential. If credentials leak, stop the companion, revoke devices, and reconfigure the affected identity. Never commit private configuration.

## Source build

Source builds require JDK 17 or 21, Android SDK Platform 35, Build Tools 34.0.0, and Platform Tools. Install the SDK components and accept their licenses in Android Studio's SDK Manager or with `sdkmanager`. Set `JAVA_HOME` and `ANDROID_HOME`, or use `sdk.dir` in the Git-ignored `local.properties` for the SDK. The included Gradle Wrapper downloads Gradle and dependencies on first build.

```powershell
python tools/setup_watch.py doctor --target build
python tools/setup_watch.py build
python tools/setup_watch.py install
```

Use `build --mirror` to explicitly enable repository mirrors if needed. Debug signing differs from the public Release key; check the installed signature before updating. Run `.\gradlew.bat :app:assembleRelease` for an unsigned release build, then sign it with your own privately backed-up key. See [Android documentation](https://developer.android.com/build/building-cmdline).

## Updating and diagnostics

- The watch checks the latest stable GitHub Release on startup and shows the newer version when available. To update, download and verify the signed APK, install it with ADB, and update the companion source to the matching version.

- Preserve your signing key and privately back up local configuration; that backup contains secrets.
- Update source and dependencies, rebuild, install with the same key, and restart this companion.
- Companion logs are in `.local/computers/<machine-key>/server.stdout.log` and `server.stderr.log`. Redact chat IDs, messages, paths, domains, hostnames and credentials before sharing.
- If a port is occupied, stop only a process verified to belong to this project. Do not terminate Codex desktop or unrelated services.
- Desktop protocol changes can make controls unavailable. Do not replace interruption or approval with an extra natural-language chat message.

See [CONTRIBUTING.md](../CONTRIBUTING.md) and [SECURITY.md](../SECURITY.md) before contributing or publishing.
