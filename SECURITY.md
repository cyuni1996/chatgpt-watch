# 安全 / Security

- 电脑身份、连接口令、证书和聊天缓存保存在本机 `.local/`；不要上传这些文件或未经脱敏的日志。
- 只与可信设备配对。局域网在手表核对电脑名称和地址后确认。外网配对使用一次性码和直达电脑 HTTPS 服务的 TCP 透传。 [外网连接](docs/INSTALL.zh-CN.md#外网连接)
- 发现漏洞时，请先与维护者约定私密反馈渠道，避免在公开 Issue 中贴凭据或敏感细节。

Runtime identities, tokens, certificates and chat caches live in local `.local/`. Keep them and unredacted logs private. Pair only trusted devices. Check the computer name and address on the watch for LAN pairing. Internet pairing uses a one-time code and TCP passthrough to the companion's HTTPS service. Arrange a private channel with the maintainer before sharing vulnerability details. [Internet connection](docs/INSTALL.en.md#internet-connection)

贡献者提交前的检查见 [开发指南](docs/DEVELOPMENT.md#提交前检查--before-publishing)。
