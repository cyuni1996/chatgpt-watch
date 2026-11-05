# 安全与隐私 / Security and privacy

## 数据在哪里 / Local data

运行身份、随机口令、TLS 私钥／证书、授权设备表、调用聊天编号及聊天显示缓存均保存在忽略的 `.local/`；使用 `WATCH_CHAT_HOME` 可改变 bridge 的运行目录，但标准启动器采用按电脑隔离的目录。这里会包含真实聊天内容和敏感连接信息。语音录音／合成文件按请求在临时目录中处理，完成后清理。手表本地保存连接令牌、证书指纹和草稿；应用关闭系统备份。

Runtime identity, tokens, TLS keys/certificates, device grants, caller chat IDs and chat display caches live in ignored `.local/`. They may contain real conversations and secrets. The bridge can use `WATCH_CHAT_HOME`, while the standard launcher chooses a per-computer directory. Speech request files use temporary directories and are cleaned afterward. The watch stores tokens, certificate pins and drafts locally, with Android backup disabled.

## 信任边界 / Trust boundary

- 只在自己控制的电脑和可信网络上运行。已授权手表可以读取聊天并请求执行桌面任务；保护手表、账号和配对确认。
- 局域网 HTTPS 固定证书指纹；公网 HTTPS 校验域名和标准证书。配对需电脑明确批准，令牌不在服务发现中广播。
- 新设备令牌按设备哈希保存；旧版共享令牌兼容独立存在。撤销新设备不会使旧共享令牌失效。
- 隧道仅接入回环地址，屏蔽管理路径；不要直接暴露局域网端口。公网并不等于无需鉴权。
- 桌面管道是版本相关实现，没有稳定性或安全审计认证保证。代码不附带 Codex 桌面内部实现。

Run only on computers and networks you control. A paired watch can read chats and request desktop tasks. Protect both endpoints and check pairing codes. LAN uses certificate pinning; public mode uses standard HTTPS validation. New device tokens are hashed separately; legacy shared credentials remain a separate compatibility mechanism. The tunnel uses loopback and blocks admin routes. These version-dependent desktop adapters have not received an independent security audit.

## 发布前 / Before publishing

```powershell
git add .
python tools/check_public_tree.py --tracked
python tools/check_public_tree.py --history
git diff --cached --stat
git diff --cached
```

检查器只输出文件路径、规则和行号，不回显疑似秘密。可通过 `--deny-file` 传入一个**仓库之外**的私有文本文件，每行一个需要精确拦截的私人标识；不要将该文件添加到项目。启发式扫描不能保证发现所有秘密，还需要人工检查文件清单、媒体和提交历史。Git author/email 也是公开信息，发布时应使用自己选择的公开署名与 GitHub 隐私邮箱。

The checker reports paths, rule names and line numbers without echoing suspected values. Optional `--deny-file` takes an external private file containing one literal identifier per line. Never commit it. Heuristics are not a guarantee: review file lists, media and history manually as well. Commit author/email are public metadata; use an intentional public name and GitHub privacy email.

禁止提交 / Do not commit:

- `.local/`, `local.properties`, `.env`, caches, logs, databases, certificates or signing keys.
- Connection/tunnel credentials, real pairing codes, screenshots of private chats, voice recordings, private project paths or device identifiers.
- APKs built with private configuration; distribute reviewed signed releases separately if needed.

如果已经泄漏秘密，先撤销／轮换；删除文件或加 `.gitignore` 不会清除历史，也不会使秘密失效。不要在公开 Issue 中提交真实令牌、完整日志或利用细节。若仓库启用了 GitHub 私密漏洞报告，请使用该入口；否则先以不含敏感细节的方式联系维护者约定私密渠道。

If a secret has leaked, revoke/rotate it first. Deleting the file or ignoring it does not remove history or invalidate the credential. Do not post tokens, full logs or exploit details in public issues. Use GitHub private vulnerability reporting if enabled; otherwise arrange a private channel with the maintainer without disclosing sensitive details publicly.
