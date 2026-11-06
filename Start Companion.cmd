@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\start-companion.ps1"
if errorlevel 1 (
    pause
    exit /b 1
)
:menu
echo.
choice /c LPQ /n /m "[L] LAN pairing  [P] Internet pairing code  [Q] Close: "
if errorlevel 3 exit /b 0
if errorlevel 2 (
    python "%~dp0tools\manage_connections.py" internet-code
    goto menu
)
if errorlevel 1 (
    python "%~dp0tools\manage_connections.py" pair
    goto menu
)
