@echo off
title AI Teleprompter - Master Launcher
setlocal enabledelayedexpansion

cd /d "%~dp0"

echo ======================================================================
echo          AI Teleprompter - Full Stack Online Launcher
echo ======================================================================
echo.

:: 1. Cleanup old / stale instances
echo [*] Cleaning up existing sessions...
taskkill /F /IM electron.exe >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8765" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)

:: 2. Determine Python Path
set "PYTHON_EXE="
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
) else (
    where python >nul 2>&1
    if !errorlevel! equ 0 (
        set "PYTHON_EXE=python"
    ) else (
        echo [!] ERROR: Python 3.11+ was not found in PATH or standard location.
        pause
        exit /b 1
    )
)

:: 3. Start Backend Server on 0.0.0.0:8765
echo [*] Starting AI Teleprompter Backend on port 8765...
start "AI Teleprompter Backend" "!PYTHON_EXE!" "%~dp0backend\main.py" --host 0.0.0.0 --port 8765

:: 4. Start ngrok tunnel (visible terminal)
set "NGROK_EXE="
if exist "%LOCALAPPDATA%\Programs\Python\Python311\Scripts\ngrok.exe" (
    set "NGROK_EXE=%LOCALAPPDATA%\Programs\Python\Python311\Scripts\ngrok.exe"
) else (
    where ngrok >nul 2>&1
    if !errorlevel! equ 0 (
        set "NGROK_EXE=ngrok"
    )
)

if defined NGROK_EXE (
    echo [*] Launching visible ngrok Cloud Tunnel window...
    start "ngrok Tunnel (salvaging-quiver-preheated.ngrok-free.dev)" "!NGROK_EXE!" http 8765 --url salvaging-quiver-preheated.ngrok-free.dev
) else (
    echo [i] ngrok CLI not found. Remote public tunneling skipped.
)

:: 5. Wait for backend to be ready
echo [*] Waiting for services to initialize...
timeout /t 3 /nobreak >nul

:: 6. Launch Desktop Application
echo [*] Launching AI Teleprompter Desktop Application...
if exist "%~dp0release\AI-Teleprompter-0.1.0-Portable.exe" (
    start "" "%~dp0release\AI-Teleprompter-0.1.0-Portable.exe"
) else if exist "%~dp0node_modules\electron\dist\electron.exe" (
    start "" "%~dp0node_modules\electron\dist\electron.exe" "%~dp0."
) else (
    start "" npx electron .
)

:: 7. Open Admin Dashboard in browser
echo [*] Opening Admin Portal at http://localhost:8765/admin ...
start "" "http://localhost:8765/admin"

echo.
echo ======================================================================
echo  All systems online!
echo  - Local Backend:   http://localhost:8765
echo  - Admin Portal:    http://localhost:8765/admin
echo  - Cloud URL:       https://salvaging-quiver-preheated.ngrok-free.dev
echo ======================================================================
echo.
timeout /t 5
exit 0
