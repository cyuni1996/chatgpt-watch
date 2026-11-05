$ErrorActionPreference = 'Stop'
$project = Split-Path -Parent $PSScriptRoot
$python = (Get-Command python).Source
$computer = (& $python (Join-Path $PSScriptRoot 'computer_runtime.py') --layout | ConvertFrom-Json)
if ($LASTEXITCODE -ne 0) { throw '无法读取本机连接配置。' }
$project = $computer.projectDirectory
$scriptPath = Join-Path (Join-Path $project 'bridge') 'server.py'
$pidFiles = @((Join-Path $computer.directory 'server.pid'), (Join-Path $project '.local/server.pid'))
foreach ($pidFile in $pidFiles) {
 if (Test-Path -LiteralPath $pidFile) {
    $serverPid = [int](Get-Content -LiteralPath $pidFile)
    $existing = Get-CimInstance Win32_Process -Filter "ProcessId=$serverPid" -ErrorAction SilentlyContinue
    if ($existing -and $existing.CommandLine -match [regex]::Escape($scriptPath)) {
        # Stop this companion and its transport child, preserving the desktop app.
        & taskkill.exe /PID $serverPid /T /F | Out-Null
        if ($LASTEXITCODE -ne 0) { throw '连接服务未能停止；保留进程记录供重试。' }
    } elseif ($existing) {
        throw '进程编号属于其他程序，未停止任何程序；请核对本工程连接服务。'
    }
    Remove-Item -LiteralPath $pidFile
 }
}
Write-Output '手表对话连接服务已停止。'
