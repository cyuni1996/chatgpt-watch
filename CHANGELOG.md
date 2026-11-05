# Changelog / 更新记录

## 0.13.0 — public source snapshot

- Shared desktop/watch conversations, per-chat drafts, project/history management, response interruption and supported approvals.
- LAN discovery and explicitly approved pairing; optional fixed-domain Cloudflare named tunnel.
- Compact model/reasoning selector, account usage display, interactive back navigation, continuous crown scrolling and configurable haptics.
- Public application identity `org.watchchat.app`, MIT code/documentation license, separately documented runtime artwork.
- Bilingual setup and maintenance instructions; ignored private runtime state; staged/history privacy checks.
- Validated: 49 Android tests, 75 bridge tests, 9 tooling tests and 11 Node tests; Android debug/release builds and lint (zero errors, existing warnings remain).
- Build validation used the explicitly enabled repository mirror after the default Maven endpoint failed its network TLS handshake. No live chat messages, desktop approvals, physical watch installation or public-tunnel end-to-end test were performed for this public snapshot.

本次为公开源码快照；公开版使用独立应用标识。私人版本的签名、连接、草稿和真实截图不包含在内。当前界面主要为中文，完整英文界面仍待贡献。
