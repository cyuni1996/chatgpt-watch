<p align="center">
  <img src="app/src/main/res/drawable-nodpi/dragon_portrait.png" width="96" alt="WatchChat icon" />
</p>

<h1 align="center">WatchChat</h1>

<p align="center">Continue your desktop Codex conversations on your wrist.</p>

<p align="center">
  <a href="https://github.com/cyuni1996/chatgpt-watch/releases/latest"><img src="https://img.shields.io/github/v/release/cyuni1996/chatgpt-watch?style=flat-square&amp;color=b59ad9" alt="Latest release" /></a>
  <img src="https://img.shields.io/badge/Wear_OS-Android_11%2B-8b74a8?style=flat-square" alt="Android 11+ watch" />
  <img src="https://img.shields.io/badge/Host-Windows-8b74a8?style=flat-square" alt="Windows host" />
  <a href="LICENSE"><img src="https://img.shields.io/badge/Code-MIT-8b74a8?style=flat-square" alt="MIT code license" /></a>
</p>

<p align="center">
  <a href="#demo">Demo</a> · <a href="#features">Features</a> · <a href="#getting-started">Get started</a> · <a href="#controls">Controls</a> · <a href="#faq">FAQ</a> · <a href="README.md">中文</a>
</p>

## Demo

https://github.com/user-attachments/assets/c6b781af-372e-4de7-a3f0-96b153650c7e

<p align="center">
  <a href="https://github.com/cyuni1996/chatgpt-watch/releases/latest"><b>Download APK</b></a> ·
  <a href="AI_INSTALL.en.md"><b>Install with AI</b></a> ·
  <a href="https://github.com/cyuni1996/chatgpt-watch/releases/download/v0.13.0/watch-demo.html">Offline demo</a>
</p>

<sub>53-second real-watch recording with fictional chats, model entries and usage values.</sub>

## Features

| Feature | What it does |
| --- | --- |
| Shared conversations | Continue the same chat on watch and computer, with the latest messages. |
| Voice and reading | Keyboard input, reviewed speech recognition, reply playback, copy and quote. |
| Stop and requests | Interrupt a response and answer supported approvals or questions. |
| Chat history | Browse by project, search, pin, rename, archive and restore. |
| Models and usage | Quickly select a model/reasoning effort and view account usage. |
| Watch interaction | Crown scrolling, interactive back navigation, font/haptic settings and a silver-violet character theme. |

Discover and pair on the LAN, or optionally use your own fixed domain and tunnel for Internet access.

## Getting started

**Requirements:** a compatible Android 11 / API 30+ watch; a Windows computer with signed-in Codex desktop, Python 3.11+ and Node.js 20+. ADB is needed to install the APK. The prebuilt release does not require Android Studio or JDK.

### Recommended: install with AI

Copy this request to an assistant with terminal access on your computer:

```text
Please install https://github.com/cyuni1996/chatgpt-watch .
Read AI_INSTALL.en.md first. Prefer the signed Release APK and verify SHA-256.
Preserve existing apps, pairing and drafts; verify by reading history.
Tell me when I must unlock the watch, enable wireless debugging or compare codes.
```

The assistant follows the [installation runbook](AI_INSTALL.en.md) to check prerequisites, install and start the companion. You still unlock the watch and compare pairing codes.

### Manual installation and other options

- **Manual setup:** [download, install and pair over LAN](docs/INSTALL.en.md).
- **Internet access:** [fixed domain and Cloudflare Tunnel](docs/INSTALL.en.md#public-connection).
- **Source changes:** [build instructions](docs/INSTALL.en.md#source-build) and [development guide](docs/DEVELOPMENT.md).

Keep the computer, Codex and companion running. Run `Start Companion.cmd` after a reboot; daily chat does not require ADB.

## Controls

| Entry | Action |
| --- | --- |
| Top-left menu | Tap to open chat history. |
| Center title | Chat details, rename, pin and archive. |
| Top-right gear | Application settings. |
| Thin row below the composer | Model/reasoning selection for the next send. |
| Send button during a response | Becomes Stop. |
| Swipe down on the header | Account usage. |
| Crown / horizontal swipe | Scroll / go back one level. |
| Long-press / double-tap messages | Message actions / jump to latest. |

## FAQ

<details>
<summary>Does the computer need to stay on?</summary>

Yes. The computer, Codex and companion must remain running. Locking is supported; sleep and shutdown are not.

</details>

<details>
<summary>Why is discovery or history unavailable?</summary>

Check mutual network reachability, the running companion, firewall and mDNS. If pairing works but history does not, check the real caller chat and desktop protocol compatibility. See [setup and diagnostics](docs/INSTALL.en.md).

</details>

<details>
<summary>Why can't I update an existing installation?</summary>

In-place updates require the same application ID and signing key. Check the APK source before doing anything destructive. The public ID is `org.watchchat.app`, separate from private builds with another ID.

</details>

<details>
<summary>What are the language and feature limits?</summary>

The UI is currently primarily Chinese; documentation is bilingual. Full attachments, code-diff review and external web login still need a computer. Desktop interfaces can change; models and usage depend on your account.

</details>

## Notice

An unofficial community project, unaffiliated with OpenAI or device manufacturers. Provided as-is, without a guarantee of compatibility with every device or future desktop version.

Code is [MIT licensed](LICENSE). See the separate [artwork terms](docs/ASSETS.md), [third-party notices](THIRD_PARTY_NOTICES.md) and [security notes](SECURITY.md). [Issues](https://github.com/cyuni1996/chatgpt-watch/issues) and [contributions](CONTRIBUTING.md) are welcome.

## Support the author

If this project makes your watch a little more useful, you're welcome to buy the author a cappuccino ☕. Thank you for using it, sharing feedback and supporting it in your own way.

<details>
<summary>Alipay / WeChat Pay</summary>

<a href="docs/media/support-cny.png"><img src="docs/media/support-cny.png" width="520" alt="Optional support QR codes for Alipay and WeChat Pay" /></a>

</details>

<details>
<summary>Cryptocurrency (BTC / ETH / USDT)</summary>

<a href="docs/media/support-crypto.png"><img src="docs/media/support-crypto.png" width="640" alt="Optional support QR codes for BTC, ETH and ERC20 USDT with network labels" /></a>

**BTC · Bitcoin mainnet**

```text
bc1qyae989cu0mx0zx2je5xtpft09dm4fwplz3g09qnarf76y3jzz5ksdh8qcw
```

**ETH / USDT · Ethereum mainnet (USDT: ERC20)**

```text
0x18fe56573647a2b7a3230181460c47b3731dba8b
```

</details>

<sub>Tips are entirely voluntary, independent of feature access, and do not include additional services. Click an image to view its original size.</sub>
