$ErrorActionPreference = 'Stop'
$project = Split-Path -Parent $PSScriptRoot
$python = (Get-Command python).Source
& $python -c "from importlib.util import find_spec; raise SystemExit(any(find_spec(name) is None for name in ('zeroconf', 'ifaddr')))"
if ($LASTEXITCODE -ne 0) {
    Write-Warning '局域网广播缺少依赖。请运行 python -m pip install -r bridge/requirements.txt，再重启连接服务。'
}
$computer = (& $python (Join-Path $PSScriptRoot 'computer_runtime.py') | ConvertFrom-Json)
if ($LASTEXITCODE -ne 0) { throw '无法读取本机连接配置。' }
$project = $computer.projectDirectory
if (-not $computer.callerThreadId) { throw '请先配置真实聊天编号：python tools/computer_runtime.py --caller-thread-id YOUR_EXISTING_CHAT_UUID，或从提供 CODEX_THREAD_ID 的 Codex 对话内启动。' }
$runtimeDir = $computer.directory
New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null
$pidFile = Join-Path $runtimeDir 'server.pid'
$scriptPath = Join-Path (Join-Path $project 'bridge') 'server.py'
if (Test-Path -LiteralPath $pidFile) {
    $serverPid = [int](Get-Content -LiteralPath $pidFile)
    $existing = Get-CimInstance Win32_Process -Filter "ProcessId=$serverPid" -ErrorAction SilentlyContinue
    if ($existing -and $existing.CommandLine -match [regex]::Escape($scriptPath)) {
        Write-Output '连接服务已经在运行。'
        Write-Output $computer.connectionAddressLines
        exit 0
    }
}
$listener = Get-NetTCPConnection -State Listen -LocalPort $computer.port -ErrorAction SilentlyContinue
if ($listener) { throw '连接端口已被其他进程占用。请先运行“停止电脑连接.cmd”停止本项目旧服务，再重试。' }
$previousHome = $env:WATCH_CHAT_HOME
$previousThread = $env:CODEX_THREAD_ID
try {
    $env:WATCH_CHAT_HOME = $runtimeDir
    if ($computer.callerThreadId) { $env:CODEX_THREAD_ID = $computer.callerThreadId }
    $process = Start-Process -FilePath $python -ArgumentList @(('"' + $scriptPath + '"'), '--port', $computer.port) -WorkingDirectory $project -WindowStyle Hidden -RedirectStandardOutput (Join-Path $runtimeDir 'server.stdout.log') -RedirectStandardError (Join-Path $runtimeDir 'server.stderr.log') -PassThru
} finally {
    $env:WATCH_CHAT_HOME = $previousHome
    $env:CODEX_THREAD_ID = $previousThread
}
$process.Id | Set-Content -LiteralPath $pidFile
Write-Output ('手表对话连接服务已启动：' + $computer.computerName)
Write-Output $computer.connectionAddressLines
