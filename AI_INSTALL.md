# 给 AI 的安装指南

[English](AI_INSTALL.en.md) · [项目介绍](README.md) · [详细手动安装](docs/INSTALL.zh-CN.md)

## 用户只需要复制这段话

建议发给**这台 Windows 电脑上的 Codex**或其他具有终端操作能力的 AI。纯网页聊天无法代替你操作本机。

```text
请帮我安装 https://github.com/cyuni1996/chatgpt-watch 。
先阅读仓库 AI_INSTALL.md，并按其中流程操作。
优先使用官方 Release 的签名 APK，下载后校验 SHA-256，避免安装不需要的 Android 构建环境。
请检查电脑依赖、连接我的手表、安装应用、启动连接服务并指导我完成局域网配对。
保留已有应用、配对和草稿，不要因签名冲突卸载或清数据，也不要关闭防火墙。
用读取历史验证连接，不发送测试聊天、不批准真实操作。
如果必须由我解锁、开启无线调试、输入当次配对码或核对连接码，请在那一步简短说明。
完成后告诉我如何开始聊天、下次如何启动，以及实际验证结果。
```

用户仍需亲自完成手表解锁、无线调试授权和两端核对码。首次安装时的调试配对码与应用连接核对码是两回事，不要公开发送到 GitHub。

## AI 执行顺序

### 1. 只读检查，选择最短安装路线

将仓库克隆到本机普通目录。检查 `python --version`、`node --version`、`codex --version` 与 ADB；使用已有工具，不依赖维护者的目录。

```powershell
git clone https://github.com/cyuni1996/chatgpt-watch.git
cd chatgpt-watch
python tools/setup_watch.py doctor --target companion --desktop
python tools/setup_watch.py doctor --target install
```

`doctor` 返回非零表示存在未满足项，读取 JSON 后补齐并重试。它不要求预先安装第三方 Python 包。电脑服务需要 Windows、Python 3.11+、Node.js 20+；`codex` 用于模型目录。API 30+ 手表安装只需 ADB 和已签名 APK，**无需 JDK、Gradle 或完整 Android Studio**。只有修改源码或下载不可用时才走构建路线。

缺少工具时使用其官方安装来源／标准包管理器，并遵守用户和当前 AI 环境的权限要求。不要默认安装系统服务、自启动、隧道或修改防火墙。

### 2. 下载并校验公开安装包

```powershell
python tools/setup_watch.py download --tag v0.13.0
```

默认从本仓库 GitHub Release 下载 `chatgpt-watch-0.13.0.apk` 与 `SHA256SUMS`，精确匹配文件名并验证哈希；下载到忽略的 `.local/downloads/v0.13.0/`。失败就停止该安装步骤，不绕过校验。

发布包使用独立公开版签名，标识为 `org.watchchat.app`。它与其他标识的私人版分开安装。同标识但不同签名的旧包无法直接覆盖：**报告冲突，保留原安装，不能自动卸载或清除数据**。

### 3. 安装到用户明确指定的手表

通过 `adb mdns services` 尝试发现已配对的手表；未发现时才询问无线调试首页的实际地址和端口。若未配对，引导用户打开配对页并运行 `adb pair`，由用户提供当次码；不要枚举地址或猜码。

```powershell
adb connect WATCH_IP:DEBUG_PORT
python tools/setup_watch.py install --apk .local/downloads/v0.13.0/chatgpt-watch-0.13.0.apk
```

安装器只接受已授权的 ADB 设备。多设备必须加 `--serial WATCH_IP:DEBUG_PORT`，没有匹配设备时不会随意选择。ADB 不在 PATH 时加 `--adb PATH_TO_ADB`。只使用 `install -r`，失败不降级为卸载重装。

### 4. 启动电脑服务，完成应用配对

```powershell
python tools/setup_watch.py deps
python tools/setup_watch.py start
python tools/setup_watch.py pair
```

- 在 Codex 当前聊天中启动时，使用当前环境真实的 `CODEX_THREAD_ID`；启动器自动保存。切勿把本指南里的示例当作真实 ID。
- 若环境没有该变量，也没有本机已保存配置，请取得真实、已存在的本地 Codex 聊天 UUID，执行 `python tools/setup_watch.py start --caller-thread-id REAL_CHAT_UUID`。其他 AI 不能伪造 UUID 绕过这一步。
- 若端口已被其他工程的服务占用，核实归属并报告；不要停止私人版、其他项目或 Codex 桌面来强占端口。
- `pair` 开启 3 分钟窗口并等待操作。让用户在手表选择 **设置 → 电脑连接 → 局域网扫描**、点击电脑、核对两端同一组码，再在电脑输入 `y`。AI 不能在未核对时自动答 `y`。
- 不自动部署公网。只有用户需要并准备了域名／隧道时才按详细文档配置。

### 5. 只读验收与交付

```powershell
python tools/setup_watch.py verify
```

验收输出只包含历史数量，不打印聊天内容或口令。检查手表能显示历史并打开用户选择的聊天；没有“发一条测试消息”的授权时，不发消息、不批准真实操作。

交付说明应包括：安装版本、实际连接模式、完成／未完成验证、如何开始聊天、电脑重启后运行 `Start Companion.cmd`、如何停止服务。电脑、Codex 与连接服务需保持运行；锁屏可用，休眠和关机不可用。每日聊天不需要 ADB。

## 源码构建备用路线

需要 JDK 17/21、Android SDK Platform 35 和 Platform Tools。用 `ANDROID_HOME`／`ANDROID_SDK_ROOT` 指向实际 SDK 后执行：

```powershell
python tools/setup_watch.py doctor --target build
python tools/setup_watch.py build
python tools/setup_watch.py install
```

网络无法访问默认仓库时，可明确使用 `build --mirror`；不要降低 TLS 验证。自行构建的 debug 包签名与公开 Release 不同，不能混作同签名升级。源码默认 release 仍为未签名；公开发布密钥不随仓库分发。
