# 安装、连接与维护

[English](INSTALL.en.md) · [返回项目首页](../README.md)

**推荐：直接使用 [AI 安装指南](../AI_INSTALL.md)。** 发布包已经签名，安装到手表只需 ADB，无需源码构建环境。以下保留完整手动和开发安装步骤。

本文维护在 `main` 分支。发布标签下的文档是该版本发布时的快照。安装时，电脑端源码和签名 APK 要使用同一发布版本。 [最新版说明](https://github.com/cyuni1996/chatgpt-watch/blob/main/docs/INSTALL.zh-CN.md) · [最新正式发布](https://github.com/cyuni1996/chatgpt-watch/releases/latest)

电脑端目前主要支持 Windows。已有安装请先阅读[升级步骤](#升级已安装的版本)。

## 安装前检查

```powershell
python --version
node --version
codex --version
adb version
```

需要 Python 3.11+、Node.js 20+、已登录的 Codex 桌面和 Android Platform Tools（ADB）。模型目录还需 PATH 中可运行的 `codex`。使用发布包不要求 JDK 或 Android Studio；虚拟环境用户请先激活环境。

## 下载并安装

使用签名 APK 时，先从 [GitHub Releases](https://github.com/cyuni1996/chatgpt-watch/releases) 选择版本，再克隆同一个发布标签。下面以 `v0.13.9` 为例：

```powershell
git clone --branch v0.13.9 https://github.com/cyuni1996/chatgpt-watch.git
cd chatgpt-watch
python tools/setup_watch.py deps
python tools/setup_watch.py download
```

下载器会校验 Release 的 SHA-256，并输出安装包路径。也可以在发布页手动下载 APK 和 `SHA256SUMS`。从开发分支拉取的源码如果没有同版本 Release，请走[源码构建](#源码构建)。手表开启无线调试后，用当次实际地址操作。无线调试的配对端口与连接端口通常不同，配对码按提示输入。

```powershell
adb pair WATCH_IP:PAIRING_PORT
adb connect WATCH_IP:DEBUG_PORT
python tools/setup_watch.py install --apk .local/downloads/v0.13.9/chatgpt-watch-0.13.9.apk
```

已配对的手表可跳过 `adb pair`。多设备时为安装器加 `--serial`，ADB 不在 PATH 时加 `--adb`。默认应用标识为 `org.watchchat.app`。覆盖更新需保持标识与签名一致。安装失败时请保留已有安装及其数据。

## 升级已安装的版本

1. 从[最新正式发布](https://github.com/cyuni1996/chatgpt-watch/releases/latest)下载签名 APK 并校验 SHA-256。应用标识和签名一致时，运行上面的安装命令即可覆盖更新并保留手表端数据。
2. 从 **GitHub 发布的 v0.13.0 升级到 v0.13.9** 时，两个版本的签名不同。确认旧版来源后，先保存需要保留的草稿，再在手表的应用管理里手动卸载旧版。卸载会清除手表端设置、草稿和配对信息。安装新版后重新配对。遇到其他签名冲突时，先核对安装包来源。
3. 在原电脑端目录停止旧连接服务，再将源码切换到与新版 APK 一致的标签。保留该目录的 `.local/`，这样电脑身份和缓存能继续使用。安装新版本依赖后运行 **Start Companion.cmd**。需要配对时，局域网按 **L**，外网按 **P**。

例如，在原电脑端仓库目录更新到 `v0.13.9`：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools/stop-companion.ps1
git fetch origin --tags
git switch --detach v0.13.9
python tools/setup_watch.py deps
```

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
3. 运行 **Start Companion.cmd**。首次添加时，在同一窗口按 **L** 开启 3 分钟配对窗口。
4. 手表进入 **设置 → 电脑连接 → 局域网扫描**，选择电脑。
5. 在手表核对电脑名称和地址，点 **确认配对**。电脑自动接受，3 分钟到期或配对成功后关闭窗口。
6. **局域网扫描**同时列出已保存和新发现的电脑，点选目标即可。地址没变时，也可在 **电脑连接** 页直接点已保存的电脑重连。

每日聊天无需开启 ADB。无线调试用于安装与更新，调试端口和聊天连接端口各自独立。首次免输码配对需要 Wi-Fi、IPv4 和 mDNS 扫描；已经配对的电脑也可用 IP 和端口手动重连。

## 外网连接

局域网和外网共用同一个电脑服务。运行 **Start Companion.cmd** 查看各网卡的内网 IP 和 TCP 端口（默认 `8766`）。把公网端口映射到穿透服务能访问的网卡 IP 和该端口，使用 TCP 透传，让手表直接校验电脑的 HTTPS 证书。

1. 在同一个 CMD 窗口按 **P**，生成一个 3 分钟有效、成功使用一次后失效的外网配对码。
2. 手表进入 **设置 → 电脑连接 → 外网连接**，填写完整 HTTPS 地址（例如 `https://203.0.113.5:24876`）和配对码。可以直接在外网首次配对。
3. 配对完成后，从电脑列表重连，无需再次输入码。回到局域网时可以扫描并点选同一台电脑；两种地址分别保存，共用原来的会话和草稿。

## 设备授权管理

```powershell
python tools/manage_connections.py devices
python tools/manage_connections.py revoke --device-id DEVICE_ID_FROM_LIST
```

每台新配对手表使用独立令牌，服务端保存哈希。旧版兼容共享令牌另行保留：撤销某个新设备不等于撤销所有旧版凭据。怀疑凭据泄漏时先停服务，撤销设备并重新配置本机身份；不要把私有配置提交到 Git。

## 源码构建

源码构建需要 JDK 17（也可用 JDK 21）、Android SDK Platform 35、Build Tools 34.0.0 和 Platform Tools。通过 Android Studio 的 SDK Manager 或 `sdkmanager` 安装这些组件并接受 SDK 许可。设置 `JAVA_HOME` 与 `ANDROID_HOME`（或本机 `local.properties` 中的 `sdk.dir`）。仓库自带 Gradle Wrapper，首次构建会下载 Gradle 和依赖。

```powershell
python tools/setup_watch.py doctor --target build
python tools/setup_watch.py build
python tools/setup_watch.py install
```

网络无法访问默认仓库时，可明确使用 `build --mirror`。debug APK 使用本机调试签名，与 Release 签名不同；覆盖更新前核对已有签名。发布构建运行 `.\gradlew.bat :app:assembleRelease`，默认输出未签名包，需用自己的私钥签名并在仓库之外备份。详见 [Android 官方说明](https://developer.android.com/build/building-cmdline)。

如果要沿用已有安装的自定义应用标识，在 Git 忽略的 `local.properties` 中设置 `watchchat.applicationId` 为原标识。已有安装确实使用了本机当前的调试密钥时，可再设置 `watchchat.signWithDebugKey=true`，让本机 Release 构建沿用该签名。构建配置和 `.local/` 下的连接资料均保留在本机。

## 更新与排查

- 手表启动时会查询 GitHub 最新正式 Release，发现新版时提示版本号。按[升级步骤](#升级已安装的版本)通过 ADB 手动安装。
- 自行构建的用户应私下备份本机配置和签名密钥。更新源码、安装依赖并重新构建后，用同一签名覆盖安装，再重启电脑端连接服务。
- 电脑服务日志位于 `.local/computers/<machine-key>/server.stdout.log` 和 `server.stderr.log`。分享之前先删掉会话、消息、路径、域名、主机名与口令。
- 同端口已有服务时只停止自己确认属于此工程的进程，不要终止 Codex 桌面或其他工程。
- 真实桌面接口变化时，部分功能可能明确报不可用。不要将停止／确认回退为新发一条聊天指令。

贡献前见 [CONTRIBUTING.md](../CONTRIBUTING.md)，公开检查见 [SECURITY.md](../SECURITY.md)。
