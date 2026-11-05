# Third-party notices / 第三方说明

The project does not relicense third-party dependencies or trademarks. Refer to each dependency's distributed license for the authoritative terms and notices. Dependencies are resolved by Gradle/pip and are not vendored here, except for the Gradle Wrapper bootstrap JAR and scripts.

The Gradle distribution's license and included notices are preserved in [LICENSES/Gradle-LICENSE.txt](LICENSES/Gradle-LICENSE.txt). The bundled wrapper JAR was checked against the Gradle 8.11.1 wrapper checksum published by Gradle.

| Component | Purpose | Upstream |
| --- | --- | --- |
| Gradle Wrapper | Build bootstrap; generated wrapper scripts include their license header | https://github.com/gradle/gradle |
| Android Gradle Plugin / Android SDK | Android build toolchain | https://developer.android.com/build |
| Kotlin | Android implementation | https://github.com/JetBrains/kotlin |
| OkHttp | Watch HTTPS client | https://github.com/square/okhttp |
| JUnit / Robolectric | Android unit tests | https://github.com/junit-team/junit4 · https://github.com/robolectric/robolectric |
| aiohttp | Companion HTTP server | https://github.com/aio-libs/aiohttp |
| cryptography | Local certificate generation | https://github.com/pyca/cryptography |
| python-zeroconf / ifaddr | LAN service discovery | https://github.com/python-zeroconf/python-zeroconf · https://github.com/ifaddr/ifaddr |
| Node.js / Python / Windows System.Speech | Host runtimes and speech components; not bundled | https://nodejs.org/ · https://www.python.org/ · https://learn.microsoft.com/dotnet/api/system.speech |
| Cloudflare Tunnel | Optional separately installed tunnel | https://github.com/cloudflare/cloudflared |

OpenAI, ChatGPT, Codex, Cloudflare, Android, Wear OS, Windows, and other product names remain their owners' trademarks. This project is not an official client or an endorsement by those owners. Codex desktop binaries, account credentials, and internal application code are not bundled.

MIT 授权不改变以上依赖、工具及商标的权利。龙娘位图素材另见 [ASSETS.md](docs/ASSETS.md)。
