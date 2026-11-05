# Contributing / 贡献说明

请先阅读 [README](README.md)、[English README](README.en.md) 和 [安全说明](SECURITY.md)。欢迎修复兼容性、改善圆屏可访问性、补充英文界面和隔离测试。

Please read both the README and security notes. Compatibility fixes, round-screen accessibility, English UI localization and isolated regressions are welcome.

1. 使用虚构的电脑、项目、聊天和令牌；测试不要连接真实桌面或自动批准真实操作。Use synthetic fixtures, not live chats or approvals.
2. 安装依赖后运行两组 Python unittest、Node tests 和 Android test/lint/build，命令见首页。Run the documented Python, Node and Android checks.
3. UI 改动检查圆屏裁切、字号、输入栏／模型栏触区、返回栈、后台停止和滚动位置。Check circular clipping, large text, touch targets, navigation, lifecycle and scroll retention.
4. 提交前运行 `python tools/check_public_tree.py --tracked`，人工检查媒体和差异。Run the public-tree checker and review media/diffs before committing.
5. 描述具体问题、修改后的行为和实际验证；注明未做的实机或公网验证。Explain the concrete behavior change, validation and any untested hardware/public-network behavior.

代码与文档贡献按本仓库 MIT 许可提交。素材贡献请附原始来源、权利人许可范围及署名要求，不能将代码许可证视为位图素材的许可证。

Code and documentation contributions use the repository's MIT license. Artwork contributions need provenance, permitted uses and attribution requirements; the code license does not license third-party artwork.
