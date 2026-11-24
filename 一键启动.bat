@echo off
setlocal
cd /d "%~dp0"
if exist "venv\Scripts\python.exe" (
    "venv\Scripts\python.exe" launch.py start
) else (
    where py >nul 2>&1
    if not errorlevel 1 (
        py -3 launch.py start
    ) else (
        python launch.py start
    )
)
set "launch_status=%errorlevel%"
if not "%launch_status%"=="0" pause
exit /b %launch_status%
