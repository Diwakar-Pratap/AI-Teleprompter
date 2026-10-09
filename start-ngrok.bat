@echo off
title ngrok Tunnel - AI Teleprompter
setlocal enabledelayedexpansion

cd /d "%~dp0"

echo ======================================================================
echo           Starting ngrok Cloud Tunnel for AI Teleprompter
echo           Target Port:  8765
echo           Custom Domain: salvaging-quiver-preheated.ngrok-free.dev
echo ======================================================================
echo.

set "NGROK_EXE="
if exist "%LOCALAPPDATA%\Programs\Python\Python311\Scripts\ngrok.exe" (
    set "NGROK_EXE=%LOCALAPPDATA%\Programs\Python\Python311\Scripts\ngrok.exe"
) else (
    where ngrok >nul 2>&1
    if !errorlevel! equ 0 (
        set "NGROK_EXE=ngrok"
    ) else (
        echo [!] ERROR: ngrok was not found in PATH or Python Scripts folder.
        pause
        exit /b 1
    )
)

echo [*] Opening ngrok tunnel...
"!NGROK_EXE!" http 8765 --url salvaging-quiver-preheated.ngrok-free.dev

pause
