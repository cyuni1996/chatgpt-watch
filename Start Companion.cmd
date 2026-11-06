@echo off
if /i "%~1"=="stop" goto stop
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0src\tools\start-companion.ps1"
if errorlevel 1 (
    if /i "%~1"=="start" exit /b 1
    pause
    exit /b 1
)
if /i "%~1"=="start" exit /b 0
:menu
echo.
choice /c LPSQ /n /m "[L] LAN pairing  [P] Internet pairing code  [S] Stop service  [Q] Close window: "
if errorlevel 4 exit /b 0
if errorlevel 3 goto stop
if errorlevel 2 (
    python "%~dp0src\tools\manage_connections.py" internet-code
    goto menu
)
if errorlevel 1 (
    python "%~dp0src\tools\manage_connections.py" pair
    goto menu
)
exit /b 1

:stop
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0src\tools\stop-companion.ps1"
exit /b %errorlevel%
