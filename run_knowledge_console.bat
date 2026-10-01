@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

rem Standalone development app: it does not start Gurumoji and does not use
rem Gurumoji's .venv or runtime/data directory.
if not defined KNOWLEDGE_CONSOLE_PORT set "KNOWLEDGE_CONSOLE_PORT=7861"
if not defined KNOWLEDGE_CONSOLE_DATA_DIR set "KNOWLEDGE_CONSOLE_DATA_DIR=%CD%\runtime\knowledge-console-dev"
rem LM Studio compatible API. If it is not running, the app falls back to the fixed default policy.
if not defined KNOWLEDGE_CONSOLE_LOCAL_LLM_URL set "KNOWLEDGE_CONSOLE_LOCAL_LLM_URL=http://127.0.0.1:1234/v1"
set "KNOWLEDGE_CONSOLE_URL=http://127.0.0.1:%KNOWLEDGE_CONSOLE_PORT%/"
rem Open the UI and the Google consent page in Chrome when it is installed;
rem set KNOWLEDGE_CONSOLE_BROWSER to another browser executable to override.
if not defined KNOWLEDGE_CONSOLE_BROWSER if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" set "KNOWLEDGE_CONSOLE_BROWSER=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if not defined KNOWLEDGE_CONSOLE_BROWSER if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" set "KNOWLEDGE_CONSOLE_BROWSER=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
if not defined KNOWLEDGE_CONSOLE_BROWSER if exist "%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe" set "KNOWLEDGE_CONSOLE_BROWSER=%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"
set "VENV_DIR=%CD%\.venv-knowledge-console"
set "REQUIREMENTS_FILE=%CD%\devtools\knowledge_console\requirements.txt"

rem If the development app is already running, only open it.
rem Windows waits about 2 seconds on a refused loopback port, so probe the
rem port briefly before the HTTP check.
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "try { $c = New-Object Net.Sockets.TcpClient; if (-not $c.ConnectAsync('127.0.0.1', %KNOWLEDGE_CONSOLE_PORT%).Wait(300)) { exit 1 }; $c.Close(); $r = Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 -Uri '%KNOWLEDGE_CONSOLE_URL%'; if ($r.StatusCode -eq 200) { exit 0 } } catch {}; exit 1" >nul 2>nul
if not errorlevel 1 (
  if defined KNOWLEDGE_CONSOLE_BROWSER (
    start "" "!KNOWLEDGE_CONSOLE_BROWSER!" "%KNOWLEDGE_CONSOLE_URL%"
  ) else (
    start "" "%KNOWLEDGE_CONSOLE_URL%"
  )
  exit /b 0
)

if not exist "%REQUIREMENTS_FILE%" (
  echo Requirements file was not found: %REQUIREMENTS_FILE%
  goto :error
)

set "BASE_PYTHON="
for %%V in (3.12 3.13 3.11 3.10) do (
  if not defined BASE_PYTHON (
    py -%%V -c "import sys; assert (3, 10) <= sys.version_info[:2] < (3, 14) and sys.maxsize > 2**32" >nul 2>nul
    if not errorlevel 1 set "BASE_PYTHON=py -%%V"
  )
)
if not defined BASE_PYTHON (
  python -c "import sys; assert (3, 10) <= sys.version_info[:2] < (3, 14) and sys.maxsize > 2**32" >nul 2>nul
  if not errorlevel 1 set "BASE_PYTHON=python"
)
if not defined BASE_PYTHON (
  echo Supported 64-bit Python 3.10 through 3.13 was not found.
  goto :error
)

if not exist "%VENV_DIR%\Scripts\python.exe" (
  echo Creating the standalone development environment in %VENV_DIR% ...
  %BASE_PYTHON% -m venv "%VENV_DIR%" || goto :error
)

set "PYTHON=%VENV_DIR%\Scripts\python.exe"
"%PYTHON%" -c "import flask, googleapiclient, google_auth_oauthlib, yaml" >nul 2>nul || (
  echo Installing the Knowledge Control Center packages ...
  "%PYTHON%" -m pip install --disable-pip-version-check -r "%REQUIREMENTS_FILE%" || goto :error
)

set "PYTHONPATH=%CD%;%PYTHONPATH%"
echo Starting the standalone Knowledge Control Center at %KNOWLEDGE_CONSOLE_URL% ...
echo Data is stored separately in %KNOWLEDGE_CONSOLE_DATA_DIR%
"%PYTHON%" -u -m devtools.knowledge_console.app || goto :error
exit /b 0

:error
set "RUN_RESULT=%ERRORLEVEL%"
if "%RUN_RESULT%"=="0" set "RUN_RESULT=1"
echo.
echo Knowledge Control Center could not be started.
pause
endlocal & exit /b %RUN_RESULT%
