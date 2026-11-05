# Installation, connections and maintenance

[中文](INSTALL.zh-CN.md) · [Project overview](../README.en.md)

**Recommended: use the [AI installation runbook](../AI_INSTALL.en.md).** The prebuilt release is already signed; installing it requires ADB, not an Android source-build toolchain. Full manual/developer instructions remain below.

Complete the README's companion dependencies, real caller chat configuration, watch build/installation, and LAN pairing first. Verify LAN history reading before setting up Internet access. The companion primarily supports Windows; equivalent speech and desktop integration are not implemented for other operating systems.

## Preflight

```powershell
python --version
node --version
codex --version
java -version
adb version
```

Python, Node and Codex must be on the launcher's PATH. Activate your Python virtual environment first if applicable. Install Android SDK Platform 35, Build Tools and Platform Tools. Android Studio can generate a local `local.properties`; never copy another developer's SDK path or commit this file.

The public app uses `org.watchchat.app`; data is not automatically migrated from a private build. A debug APK is suitable for local testing. For distribution, create and privately back up your own release key. An APK signed with a different key cannot update an installed copy in place.

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
3. Run `python tools/manage_connections.py pair`.
4. On the watch open **设置 → 电脑连接 → 局域网扫描** (Settings → Computer connection → LAN scan).
5. Compare both codes and enter `y` on the computer only if they match. The pairing window expires after three minutes. Discovery does not broadcast authentication tokens.
6. If the computer's LAN address changes, scan the same computer again. Manage saved addresses and connection modes from the connection page.

Daily communication does not require ADB. Wireless debugging is only for app installation/updates; changing its port does not change the companion's application port. Discovery requires IPv4 and mDNS multicast. Advanced manual pairing remains available for unsupported networks; never paste real connection tokens into public issues.

## Public connection

You need your own fixed domain, such as `chat.example.com`, and an online computer. This procedure uses a locally managed Cloudflare named tunnel. No tunnel, hosted server, or domain is bundled.

1. Manage the domain's DNS through Cloudflare and install the official `cloudflared` client.
2. Authenticate, create a named tunnel, and create its DNS route:

```powershell
cloudflared tunnel login
cloudflared tunnel create watch-chat
cloudflared tunnel route dns watch-chat chat.example.com
```

3. Use the returned tunnel UUID and actual credentials file path:

```powershell
python tools/configure_public.py --domain chat.example.com --tunnel-id YOUR_TUNNEL_UUID --credentials-file "C:\path\to\YOUR_TUNNEL_UUID.json"
```

The tool validates the tunnel ID against the credentials and writes local `public-endpoint.json` and `cloudflared.yml`. It does not create DNS records or a tunnel.

4. Restart the companion and start the tunnel:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools/stop-companion.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools/start-companion.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools/start-public-tunnel.ps1
```

5. Open a pairing window. Select **公网连接** (Public connection) on the watch, enter the fixed HTTPS domain, and compare both codes before approving. The watch needs its own working Internet connection.
6. Switch to a different network and confirm that the same conversation can be read. Configuration generation alone is not an end-to-end public connectivity test.

External transport uses the domain's HTTPS certificate. The tunnel forwards only to loopback `127.0.0.1:8767`; LAN stays on pinned HTTPS port 8766. No inbound router port forwarding is needed. The generated tunnel blocks `/api/connect/admin/`; management also requires a local source and a separate admin token.

The current watch client cannot complete Cloudflare Access or other browser-login challenges. Replace all example values, and do not bypass external HTTPS certificate validation with `noTLSVerify`. Stop the tunnel without affecting LAN access:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools/stop-public-tunnel.ps1
```

Reference: [Cloudflare named tunnel setup](https://developers.cloudflare.com/tunnel/features/locally-managed-tunnels/create-local-tunnel/).

## Device authorization

```powershell
python tools/manage_connections.py devices
python tools/manage_connections.py revoke --device-id DEVICE_ID_FROM_LIST
```

Newly paired watches receive independent tokens whose hashes are stored server-side. Legacy shared-token compatibility is separate: revoking one newly paired device does not revoke every old credential. If credentials leak, stop the companion, revoke devices, and reconfigure the affected identity. Never commit private configuration.

## Updating and diagnostics

- Preserve your signing key and privately back up local configuration; that backup contains secrets.
- Update source and dependencies, rebuild, install with the same key, and restart this companion.
- Logs: `.local/computers/<machine-key>/server.stdout.log` and `server.stderr.log`; tunnel logs are in the same directory. Redact chat IDs, messages, paths, domains, hostnames and credentials before sharing.
- If a port is occupied, stop only a process verified to belong to this project. Do not terminate Codex desktop or unrelated services.
- Desktop protocol changes can make controls unavailable. Do not replace interruption or approval with an extra natural-language chat message.

See [CONTRIBUTING.md](../CONTRIBUTING.md) and [SECURITY.md](../SECURITY.md) before contributing or publishing.
