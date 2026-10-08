@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0"

:: Terminate any stale electron processes from previous runs
taskkill /F /IM electron.exe >nul 2>&1

:: Terminate any orphaned backend process on port 8765 to guarantee a clean session
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8765" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)

:: Build production assets if missing
if not exist "out\main\index.js" (
    echo Building application...
    call npm run build
)

:: Find pythonw or python
set "PYTHON_EXE="
if exist "%LOCALAPPDATA%\Programs\Python\Python311\pythonw.exe" (
    set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python311\pythonw.exe"
) else (
    where pythonw >nul 2>&1
    if !errorlevel! equ 0 (
        set "PYTHON_EXE=pythonw"
    ) else (
        set "PYTHON_EXE=python"
    )
)

:: Launch fresh backend silently as background process
start "" "!PYTHON_EXE!" "%~dp0backend\main.py" --host 127.0.0.1 --port 8765

:: Launch Electron GUI executable directly and close CMD immediately
if exist "%~dp0node_modules\electron\dist\electron.exe" (
    start "" "%~dp0node_modules\electron\dist\electron.exe" "%~dp0."
) else (
    start "" npx electron .
)

exit 0
