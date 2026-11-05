# 安装、连接与维护

[English](INSTALL.en.md) · [返回项目首页](../README.md)

**推荐：直接使用 [AI 安装指南](../AI_INSTALL.md)。** 发布包已经签名，安装到手表只需 ADB，无需源码构建环境。以下保留完整手动和开发安装步骤。

以下步骤可独立完成首次安装。建议先验证局域网读取历史，再配置公网。电脑端目前主要支持 Windows。

## 安装前检查

```powershell
python --version
node --version
codex --version
adb version
```

需要 Python 3.11+、Node.js 20+、已登录的 Codex 桌面和 Android Platform Tools（ADB）。模型目录还需 PATH 中可运行的 `codex`。使用发布包不要求 JDK 或 Android Studio；虚拟环境用户请先激活环境。

## 下载并安装

在 PowerShell 中将工程克隆到本机普通目录，安装电脑依赖并下载签名 APK：

```powershell
git clone https://github.com/cyuni1996/chatgpt-watch.git
cd chatgpt-watch
python tools/setup_watch.py deps
python tools/setup_watch.py download --tag v0.13.0
```

下载器会校验 Release 的 SHA-256。手表开启无线调试后，用当次实际地址操作；配对端口与调试端口通常不同，配对码按提示输入：

```powershell
adb pair WATCH_IP:PAIRING_PORT
adb connect WATCH_IP:DEBUG_PORT
python tools/setup_watch.py install --apk .local/downloads/v0.13.0/chatgpt-watch-0.13.0.apk
```

已配对的手表可跳过 `adb pair`。多设备时为安装器加 `--serial`，ADB 不在 PATH 时加 `--adb`。公开版标识为 `org.watchchat.app`；覆盖更新需保持标识与签名一致。安装失败时不要自动卸载或清除数据。

## 调用聊天配置与服务生命周期

桌面工具必须有真实调用会话：

```powershell
python tools/computer_runtime.py --caller-thread-id YOUR_EXISTING_CHAT_UUID --name "My PC"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools/start-companion.ps1
```

若从 Codex 内的工程上下文启动且提供 `CODEX_THREAD_ID`，可自动保存；手动填写时 UUID 格式检查只验证格式，不保证该聊天存在或可访问。编号无效会造成历史读取或创建失败。

每台电脑使用 `.local/computers/<machine-key>/` 的独立身份。复制公开源码到第二台电脑后应重新配对；不要复制 `.local`。默认机器名来自系统主机名，可通过 `--name` 设置不包含个人信息的别名。启动命令只输出启动信息，不证明 Codex 协议已连通，应以手表实际读取历史为准。

停止本工程服务：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools/stop-companion.ps1
```

服务运行期间连接启动一次即可，电脑重启后需再次启动。当前不配置托盘应用、计划任务或系统服务。停止后已提交的 Codex 任务可能继续运行；需要停止回复时请使用对应聊天的停止按钮。

## 局域网连接

1. 电脑与手表接入可互访网络，避免访客网络设备隔离。
2. Windows 防火墙只在可信网络允许该 Python 程序的 TCP 8766 和 mDNS UDP 5353，不需要关闭整个防火墙。
3. 运行 `python tools/manage_connections.py pair`。
4. 手表进入 **设置 → 电脑连接 → 局域网扫描**，选择电脑。
5. 比较两端核对码，在电脑输入 `y` 批准。窗口 3 分钟后关闭；设备发现不广播口令。
6. 电脑地址变化时重新扫描同一电脑。已有电脑的模式和地址可在连接页管理。

每日聊天不需要开启 ADB。无线调试只用于安装与更新；调试端口变化与应用连接端口无关。扫描要求 IPv4 与 mDNS 多播，不支持的网络可使用高级手动配对，但不要将真实令牌粘贴到公开问题中。

## 公网连接

公网模式需要你自己的固定域名，例如 `chat.example.com`，并且电脑在线。以下为本地管理的 Cloudflare 命名隧道方案；没有预装隧道或代管服务器。

1. 将域名接入 Cloudflare DNS，安装官方 `cloudflared`。
2. 登录并创建命名隧道和 DNS 路由：

```powershell
cloudflared tunnel login
cloudflared tunnel create watch-chat
cloudflared tunnel route dns watch-chat chat.example.com
```

3. 用创建命令返回的 UUID 与真实凭据文件路径配置工程：

```powershell
python tools/configure_public.py --domain chat.example.com --tunnel-id YOUR_TUNNEL_UUID --credentials-file "C:\path\to\YOUR_TUNNEL_UUID.json"
```

工具验证凭据与隧道编号一致，只写入本机 `public-endpoint.json` 和 `cloudflared.yml`；它不会创建 DNS 或隧道。

4. 重启电脑连接服务，再启动隧道：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools/stop-companion.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools/start-companion.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools/start-public-tunnel.ps1
```

5. 打开配对窗口，手表选择 **公网连接** 并填写固定 HTTPS 域名，两端核对码后允许。需要手表自身具备可用的互联网连接。
6. 切换到另一网络验证读取同一聊天；没有域名和真实外网测试前，不能认为公网已部署成功。

公网 HTTPS 由域名证书提供。隧道只转发到电脑回环地址 `127.0.0.1:8767`，局域网仍使用证书固定的 HTTPS 8766。无需路由器入站端口映射。隧道配置屏蔽 `/api/connect/admin/` 管理路径；管理还要求本机来源和独立管理口令。

当前客户端不支持 Cloudflare Access 等网页登录挑战。不要将示例域名原样使用，也不要配置 `noTLSVerify` 来绕过外部 HTTPS 校验。关闭隧道不会关闭局域网连接：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools/stop-public-tunnel.ps1
```

参考：[Cloudflare 命名隧道](https://developers.cloudflare.com/tunnel/features/locally-managed-tunnels/create-local-tunnel/)。

## 设备授权管理

```powershell
python tools/manage_connections.py devices
python tools/manage_connections.py revoke --device-id DEVICE_ID_FROM_LIST
```

每台新配对手表使用独立令牌，服务端保存哈希。旧版兼容共享令牌另行保留：撤销某个新设备不等于撤销所有旧版凭据。怀疑凭据泄漏时先停服务，撤销设备并重新配置本机身份；不要把私有配置提交到 Git。

## 源码构建

仅修改源码时需要 JDK 17/21、Android SDK Platform 35、Build Tools 和 Platform Tools。设置 `JAVA_HOME` 与 `ANDROID_HOME`（或本机 `local.properties` 中的 `sdk.dir`），然后运行：

```powershell
python tools/setup_watch.py doctor --target build
python tools/setup_watch.py build
python tools/setup_watch.py install
```

网络无法访问默认仓库时，可明确使用 `build --mirror`。debug APK 使用本机调试签名，与 Release 签名不同；覆盖更新前核对已有签名。发布构建运行 `.\gradlew.bat :app:assembleRelease`，默认输出未签名包，需用自己的私钥签名并在仓库之外备份。详见 [Android 官方说明](https://developer.android.com/build/building-cmdline)。

## 更新与排查

- 更新前保留签名密钥，备份本机配置到私有位置；备份中含秘密。
- 更新源码、安装依赖、重新构建，用同一签名覆盖安装；重启本工程连接服务。
- 日志：`.local/computers/<machine-key>/server.stdout.log` 和 `server.stderr.log`；隧道日志位于同目录。分享之前先删掉会话、消息、路径、域名、主机名与口令。
- 同端口已有服务时只停止自己确认属于此工程的进程，不要终止 Codex 桌面或其他工程。
- 真实桌面接口变化时，部分功能可能明确报不可用。不要将停止／确认回退为新发一条聊天指令。

贡献前见 [CONTRIBUTING.md](../CONTRIBUTING.md)，公开检查见 [SECURITY.md](../SECURITY.md)。
