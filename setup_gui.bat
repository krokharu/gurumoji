@echo off
setlocal EnableExtensions
cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup_gui.ps1"
set "SETUP_RESULT=%ERRORLEVEL%"
if not "%SETUP_RESULT%"=="0" (
  echo.
  echo The setup window could not be opened. See the message above.
  pause
)
endlocal & exit /b %SETUP_RESULT%
