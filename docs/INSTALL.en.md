# Installation, connections and maintenance

[中文](INSTALL.zh-CN.md) · [Project overview](README.en.md)

**Recommended: use the [AI installation runbook](AI_INSTALL.en.md).** The prebuilt release is already signed; installing it requires ADB, not an Android source-build toolchain. Full manual/developer instructions remain below.

This guide is maintained on `main`. A tagged copy is the documentation snapshot for that release. Use the same release for the companion source and signed APK. [Current guide](https://github.com/cyuni1996/chatgpt-watch/blob/main/docs/INSTALL.en.md) · [Latest stable release](https://github.com/cyuni1996/chatgpt-watch/releases/latest)

The companion primarily supports Windows. If the app is already installed, see [the upgrade steps](#upgrading-an-existing-installation) first.

Run these PowerShell commands from the repository root. The examples detect both the older tag layout and the current layout. Replace `PATH_TO_VERIFIED_APK` with the path printed by the downloader.

## Preflight

```powershell
python --version
node --version
codex --version
adb version
```

Use Python 3.11+, Node.js 20+, signed-in Codex desktop and Android Platform Tools (ADB). The model catalog also requires `codex` on PATH. The prebuilt APK does not require JDK or Android Studio. Activate your virtual environment first if applicable.

## Download and install

Choose a [GitHub release](https://github.com/cyuni1996/chatgpt-watch/releases), then clone the matching Git tag in PowerShell. The example uses `v0.13.10`.

```powershell
git clone --branch v0.13.10 https://github.com/cyuni1996/chatgpt-watch.git
cd chatgpt-watch
$setup = if (Test-Path packaging/setup_watch.py) { "packaging/setup_watch.py" } else { "tools/setup_watch.py" }
python $setup deps
python $setup download
```

The downloader verifies the release SHA-256 and prints the APK path. You can also download the APK and `SHA256SUMS` from the release page. For a development checkout without a matching release, see [source build](#source-build). Enable wireless debugging on the watch and use its current addresses. The wireless debugging pairing and connection ports usually differ.

```powershell
adb pair WATCH_IP:PAIRING_PORT
adb connect WATCH_IP:DEBUG_PORT
python $setup install --apk "PATH_TO_VERIFIED_APK"
```

Skip `adb pair` for an already paired watch. Add `--serial` for multiple devices and `--adb` when ADB is not on PATH. The public app ID is `org.watchchat.app`; in-place updates need the same ID and signing key. Never automatically uninstall or clear data after an installation failure.

## Upgrading an existing installation

1. Download the signed APK from the [latest stable release](https://github.com/cyuni1996/chatgpt-watch/releases/latest) and verify its SHA-256. When the application ID and signing key match, the installation command above updates the app in place and retains watch data. v0.13.9 and v0.13.10 use the same signing key.
2. The **GitHub releases v0.13.0 and v0.13.10** use different signing keys. Verify where the old app came from, save any drafts you need, and manually uninstall it from the watch's app settings. Uninstalling clears local settings, drafts and pairings. Pair again after installing the new APK. For other signature conflicts, verify the installation source first.
3. Stop the old companion from its existing directory, then switch that checkout to the tag matching the new APK. Keep its `.local/` directory to retain the computer identity and cache. Install the new version's dependencies and run **Start Companion.cmd**. Press **L** for LAN pairing or **P** for Internet pairing when needed.

For example, to update to `v0.13.10` from the existing companion checkout:

```powershell
$stop = if (Test-Path src/tools/stop-companion.ps1) { "src/tools/stop-companion.ps1" } else { "tools/stop-companion.ps1" }
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $stop
git fetch origin --tags
git switch --detach v0.13.10
$setup = if (Test-Path packaging/setup_watch.py) { "packaging/setup_watch.py" } else { "tools/setup_watch.py" }
python $setup deps
```

## Caller context and lifecycle

Desktop tools require a real existing local caller chat:

```powershell
python $setup start --caller-thread-id YOUR_EXISTING_CHAT_UUID --name "My PC"
```

Starting from a Codex project context can automatically save `CODEX_THREAD_ID` when that environment variable is provided. UUID validation checks syntax only; it does not prove the chat exists or is accessible. An invalid caller can prevent history reading or chat creation.

Each computer uses an independent identity in `.local/computers/<machine-key>/`. Copy source code, not `.local`, when setting up another computer, and pair it separately. The default computer name comes from the OS hostname; use `--name` to choose a non-personal alias. A successful process launch does not prove desktop protocol connectivity; verify actual history on the watch.

Stop only this project's companion with:

```powershell
$stop = if (Test-Path src/tools/stop-companion.ps1) { "src/tools/stop-companion.ps1" } else { "tools/stop-companion.ps1" }
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $stop
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
$manage = if (Test-Path src/tools/manage_connections.py) { "src/tools/manage_connections.py" } else { "tools/manage_connections.py" }
python $manage devices
python $manage revoke --device-id DEVICE_ID_FROM_LIST
```

Newly paired watches receive independent tokens whose hashes are stored server-side. Legacy shared-token compatibility is separate: revoking one newly paired device does not revoke every old credential. If credentials leak, stop the companion, revoke devices, and reconfigure the affected identity. Never commit private configuration.

## Source build

These build paths describe the current checkout layout. For older tags, use the paths documented at that tag.

Source builds require JDK 17 or 21, Android SDK Platform 35, Build Tools 34.0.0, and Platform Tools. Install the SDK components and accept their licenses in Android Studio's SDK Manager or with `sdkmanager`. Set `JAVA_HOME` and `ANDROID_HOME`, or use `sdk.dir` in the Git-ignored `packaging/local.properties` for the SDK. The included Gradle Wrapper downloads Gradle and dependencies on first build.

```powershell
python packaging/setup_watch.py doctor --target build
python packaging/setup_watch.py build
python packaging/setup_watch.py install
```

Use `build --mirror` to explicitly enable repository mirrors if needed. Debug signing differs from the public Release key; check the installed signature before updating. Run `.\packaging\gradlew.bat -p packaging :app:assembleRelease` for an unsigned release build, then sign it with your own privately backed-up key. See [Android documentation](https://developer.android.com/build/building-cmdline).

For an existing custom application ID, set `watchchat.applicationId` in the Git-ignored `packaging/local.properties`. If the installed app uses this computer's current debug key, set `watchchat.signWithDebugKey=true` to use it for the local Release build. Keep build settings and connection data on this computer.

## Updating and diagnostics

- On startup, the watch checks GitHub for the latest stable release and shows the newer version when available. Follow the [upgrade steps](#upgrading-an-existing-installation) to install it manually with ADB.
- If you build from source, back up your local configuration and signing key privately. Update the source and dependencies, rebuild, install with the same key, and restart the companion.
- Companion logs are in `.local/computers/<machine-key>/server.stdout.log` and `server.stderr.log`. Redact chat IDs, messages, paths, domains, hostnames and credentials before sharing.
- If a port is occupied, stop only a process verified to belong to this project. Do not terminate Codex desktop or unrelated services.
- Desktop protocol changes can make controls unavailable. Do not replace interruption or approval with an extra natural-language chat message.

See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md) before contributing or publishing.
