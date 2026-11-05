$ErrorActionPreference = 'Stop'
$project = Split-Path -Parent $PSScriptRoot
$layout = (& python (Join-Path $PSScriptRoot 'computer_runtime.py') --layout | ConvertFrom-Json)
$configFile = Join-Path $layout.directory 'cloudflared.yml'
if (-not (Test-Path -LiteralPath $configFile)) { throw '尚未配置公网域名。请先按使用说明运行 tools/configure_public.py。' }
$cloudflared = (Get-Command cloudflared -ErrorAction Stop).Source
$pidFile = Join-Path $layout.directory 'tunnel.pid'
if (Test-Path -LiteralPath $pidFile) {
    $tunnelPid = [int](Get-Content -LiteralPath $pidFile)
    $existing = Get-CimInstance Win32_Process -Filter "ProcessId=$tunnelPid" -ErrorAction SilentlyContinue
    if ($existing -and $existing.CommandLine -match [regex]::Escape($configFile)) { Write-Output '公网隧道已在运行。';exit 0 }
}
$process = Start-Process -FilePath $cloudflared -ArgumentList @('tunnel','--config',('"'+$configFile+'"'),'run') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $layout.directory 'tunnel.stdout.log') -RedirectStandardError (Join-Path $layout.directory 'tunnel.stderr.log')
$process.Id | Set-Content -LiteralPath $pidFile
Write-Output '公网隧道已启动。'
