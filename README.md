<p align="center">
  <img src="app/src/main/res/drawable-nodpi/dragon_portrait.png" width="96" alt="WatchChat 图标" />
</p>

<h1 align="center">WatchChat</h1>

<p align="center">在手表上，继续电脑里的 Codex 对话。</p>

<p align="center">
  <a href="https://github.com/cyuni1996/chatgpt-watch/releases/latest"><img src="https://img.shields.io/github/v/release/cyuni1996/chatgpt-watch?style=flat-square&amp;color=b59ad9" alt="最新版本" /></a>
  <img src="https://img.shields.io/badge/Wear_OS-Android_11%2B-8b74a8?style=flat-square" alt="Android 11 及以上手表" />
  <img src="https://img.shields.io/badge/电脑端-Windows-8b74a8?style=flat-square" alt="Windows 电脑端" />
  <a href="LICENSE"><img src="https://img.shields.io/badge/代码-MIT-8b74a8?style=flat-square" alt="代码 MIT 许可" /></a>
</p>

<p align="center">
  <a href="#演示">演示</a> · <a href="#功能">功能</a> · <a href="#开始使用">开始使用</a> · <a href="#操作速查">操作速查</a> · <a href="#常见问题">常见问题</a> · <a href="README.en.md">English</a>
</p>

## 演示

https://github.com/user-attachments/assets/c6b781af-372e-4de7-a3f0-96b153650c7e

<p align="center">
  <a href="https://github.com/cyuni1996/chatgpt-watch/releases/latest"><b>下载 APK</b></a> ·
  <a href="AI_INSTALL.md"><b>让 AI 帮我安装</b></a> ·
  <a href="https://github.com/cyuni1996/chatgpt-watch/releases/download/v0.13.0/watch-demo.html">离线演示页</a>
</p>

<sub>53 秒实机录屏；聊天、模型和额度为演示数据。</sub>

## 功能

| 功能 | 说明 |
| --- | --- |
| 双向续聊 | 手表与电脑继续同一段聊天，查看最新消息。 |
| 语音与阅读 | 键盘输入、语音识别后确认发送、回复朗读、复制与引用。 |
| 停止与确认 | 停止当前回复，在手表上回答支持的操作确认与选择题。 |
| 历史管理 | 按项目浏览、搜索、置顶、重命名、归档及恢复。 |
| 模型与额度 | 底部快捷切换模型和思考强度，查看账号额度。 |
| 手表交互 | 表冠滚动、跟手返回、可调字号与触感、银紫龙娘主题。 |

支持局域网扫描配对，也可选配自己的固定域名与隧道实现公网连接。

## 开始使用

**运行条件：** Android 11 / API 30+ 的兼容手表；Windows 电脑上已登录 Codex，安装 Python 3.11+ 和 Node.js 20+。安装 APK 需要 ADB；使用发布包不需要 Android Studio 或 JDK。

### 推荐：交给 AI 安装

把下面这段话复制给电脑上有终端权限的 AI：

```text
请帮我安装 https://github.com/cyuni1996/chatgpt-watch 。
先阅读 AI_INSTALL.md，优先下载 Release 签名 APK 并校验 SHA-256。
保留已有应用、配对和草稿，用读取历史验证连接。
需要我解锁手表、开启无线调试或核对配对码时，再提示我。
```

AI 按 [安装指南](AI_INSTALL.md)检查环境、安装应用并启动连接服务；首次解锁与核对码仍由你完成。

### 手动安装与其他方式

- **手动安装：** [下载、安装与局域网配对](docs/INSTALL.zh-CN.md)。
- **外网使用：** [固定域名与 Cloudflare 隧道](docs/INSTALL.zh-CN.md#公网连接)。
- **修改源码：** [构建说明](docs/INSTALL.zh-CN.md#源码构建)与[开发指南](docs/DEVELOPMENT.md)。

日常使用时，保持电脑、Codex 和连接服务运行。电脑重启后运行 `Start Companion.cmd`；日常聊天不需要 ADB。

## 操作速查

| 入口 | 操作 |
| --- | --- |
| 左上角菜单 | 点击打开历史聊天。 |
| 中间标题 | 查看对话详情，管理名称、置顶与归档。 |
| 右上角齿轮 | 打开应用设置。 |
| 输入框下方细栏 | 切换模型和思考强度，下次发送生效。 |
| 回复中的发送按钮 | 变为停止按钮。 |
| 顶栏向下滑 | 查看额度。 |
| 表冠／横滑 | 滚动／逐级返回。 |
| 长按消息／双击正文 | 消息操作／回到最新。 |

## 常见问题

<details>
<summary>电脑需要一直开着吗？</summary>

需要保持电脑、Codex 和连接服务运行。锁屏可用，休眠或关机后不可用。

</details>

<details>
<summary>扫描不到电脑，或者连上后看不到历史？</summary>

先确认两端网络可互访、电脑服务已运行，再核对防火墙与 mDNS。能配对却无法读取历史时，检查真实调用会话和桌面协议兼容性，见[安装与排查](docs/INSTALL.zh-CN.md)。

</details>

<details>
<summary>已有版本无法覆盖安装怎么办？</summary>

覆盖更新需要相同的应用标识和签名。先确认安装包来源；不要直接卸载或清数据。公开版标识为 `org.watchchat.app`，与其他标识的私人版分开安装。

</details>

<details>
<summary>界面语言和功能有哪些限制？</summary>

当前界面主要为中文，文档提供中英文。完整附件、代码差异审阅和外部网页登录仍需电脑。桌面接口随版本变化，模型和额度按实际账号提供。

</details>

## 说明

非官方社区项目，与 OpenAI 及设备厂商无隶属关系。软件按原样提供，不保证适配所有设备或持续兼容桌面接口。

代码采用 [MIT](LICENSE) 许可。美术素材、第三方组件和安全信息分别见[素材说明](docs/ASSETS.md)、[第三方说明](THIRD_PARTY_NOTICES.md)与[安全说明](SECURITY.md)。欢迎提交 [Issue](https://github.com/cyuni1996/chatgpt-watch/issues) 或[参与贡献](CONTRIBUTING.md)。

## 支持作者

如果这个项目让你的手表更顺手，欢迎自愿请作者喝一杯卡布奇诺 ☕。感谢你的使用、反馈和每一份支持。

<details>
<summary>展开赞赏码（支付宝 / 微信）</summary>

赞赏完全随心，与功能使用无关，也不附带额外服务承诺。

<img src="docs/media/support.png" width="480" alt="自愿赞赏：支付宝与微信收款码" />

</details>
