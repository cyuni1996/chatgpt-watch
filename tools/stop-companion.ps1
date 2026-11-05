$ErrorActionPreference = 'Stop'
$project = Split-Path -Parent $PSScriptRoot
$python = (Get-Command python).Source
$computer = (& $python (Join-Path $PSScriptRoot 'computer_runtime.py') --layout | ConvertFrom-Json)
if ($LASTEXITCODE -ne 0) { throw '无法读取本机连接配置。' }
$scriptPath = Join-Path $project 'bridge/server.py'
$pidFiles = @((Join-Path $computer.directory 'server.pid'), (Join-Path $project '.local/server.pid'))
foreach ($pidFile in $pidFiles) {
 if (Test-Path -LiteralPath $pidFile) {
    $serverPid = [int](Get-Content -LiteralPath $pidFile)
    $existing = Get-CimInstance Win32_Process -Filter "ProcessId=$serverPid" -ErrorAction SilentlyContinue
    if ($existing -and $existing.CommandLine -match [regex]::Escape($scriptPath)) {
        # Stop this companion and its transport child, preserving the desktop app.
        & taskkill.exe /PID $serverPid /T /F | Out-Null
    }
    Remove-Item -LiteralPath $pidFile
 }
}
Write-Output '手表对话连接服务已停止。'
