# 安装、连接与维护

[English](INSTALL.en.md) · [返回项目首页](../README.md)

**推荐：直接使用 [AI 安装指南](../AI_INSTALL.md)。** 发布包已经签名，安装到手表只需 ADB，无需源码构建环境。以下保留完整手动和开发安装步骤。

先完成首页的电脑依赖、真实调用聊天编号配置、APK 构建与安装、局域网配对。建议先验证局域网读取历史，再配置公网。当前主要支持 Windows 电脑；其他系统未实现等价的语音和桌面协议支持。

## 安装前检查

```powershell
python --version
node --version
codex --version
java -version
adb version
```

Python、Node 和 Codex 应能从启动脚本使用的 PATH 找到。虚拟环境用户应先激活环境。Android SDK 安装 Platform 35、Build Tools 和 Platform Tools。Android Studio 能生成本机 `local.properties`；不要复制其他人的 SDK 目录配置。

使用公开版独立标识 `org.watchchat.app`；其数据不会自动从私人版迁移。初次安装推荐 debug APK 便于本机测试。长期分发请建立自己的正式签名并备份到仓库之外；签名不一致时无法直接覆盖安装。

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

## 更新与排查

- 更新前保留签名密钥，备份本机配置到私有位置；备份中含秘密。
- 更新源码、安装依赖、重新构建，用同一签名覆盖安装；重启本工程连接服务。
- 日志：`.local/computers/<machine-key>/server.stdout.log` 和 `server.stderr.log`；隧道日志位于同目录。分享之前先删掉会话、消息、路径、域名、主机名与口令。
- 同端口已有服务时只停止自己确认属于此工程的进程，不要终止 Codex 桌面或其他工程。
- 真实桌面接口变化时，部分功能可能明确报不可用。不要将停止／确认回退为新发一条聊天指令。

贡献前见 [CONTRIBUTING.md](../CONTRIBUTING.md)，公开检查见 [SECURITY.md](../SECURITY.md)。
