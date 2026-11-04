@echo off
REM ============================================================================
REM UC10 Document Anonymizer — Windows Batch Launcher
REM ============================================================================
cd /d "%~dp0"
echo Starten van UC10 Document Anonymizer Installer...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
if %ERRORLEVEL% neq 0 (
    echo.
    echo Installatie is gestopt met foutcode %ERRORLEVEL%.
    pause
    exit /b %ERRORLEVEL%
)
pause
