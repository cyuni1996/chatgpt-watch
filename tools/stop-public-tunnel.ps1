$ErrorActionPreference = 'Stop'
$layout = (& python (Join-Path $PSScriptRoot 'computer_runtime.py') --layout | ConvertFrom-Json)
$pidFile = Join-Path $layout.directory 'tunnel.pid'
$configFile = Join-Path $layout.directory 'cloudflared.yml'
if (Test-Path -LiteralPath $pidFile) {
    $tunnelPid = [int](Get-Content -LiteralPath $pidFile)
    $existing = Get-CimInstance Win32_Process -Filter "ProcessId=$tunnelPid" -ErrorAction SilentlyContinue
    if ($existing -and $existing.Name -eq 'cloudflared.exe' -and $existing.CommandLine -match [regex]::Escape($configFile)) { Stop-Process -Id $tunnelPid }
    Remove-Item -LiteralPath $pidFile
}
Write-Output '本项目公网隧道已停止。'
