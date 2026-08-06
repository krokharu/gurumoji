@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

cls
echo.
echo   CREATED BY KUROKAWA
>nul 2>nul powershell -NoProfile -Command "Start-Sleep -Milliseconds 200"
cls
echo.
echo ============================================================
echo   STARTING GURUMOJI...
echo   CHECKING FOR UPDATES...
echo ============================================================
echo.

if /I not "%MOJIOKOSI_SKIP_UPDATE_CHECK%"=="1" call :check_for_updates

rem Keep the complete Python environment inside this project folder.
set "VENV_DIR=%CD%\.venv"
set "REQUIREMENTS_FILE=%CD%\requirements.txt"
set "REQUIREMENTS_HASH="
if not exist "%REQUIREMENTS_FILE%" (
  echo requirements.txt was not found: %REQUIREMENTS_FILE%
  goto :error
)
for /f "skip=1 tokens=*" %%H in ('certutil -hashfile "%REQUIREMENTS_FILE%" SHA256 2^>nul') do (
  if not defined REQUIREMENTS_HASH set "REQUIREMENTS_HASH=%%H"
)
set "REQUIREMENTS_HASH=%REQUIREMENTS_HASH: =%"
if not defined REQUIREMENTS_HASH (
  echo Could not calculate the requirements.txt fingerprint.
  goto :error
)
set "SETUP_MARKER=%VENV_DIR%\.setup_cuda128_torch280_%REQUIREMENTS_HASH%"
set "HF_HUB_DISABLE_SYMLINKS_WARNING=1"
set "RUN_RESULT=0"

rem Prefer Python 3.12, but detect any supported 64-bit Python 3.10 through 3.13.
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

where ffmpeg >nul 2>nul || (
  echo ffmpeg was not found in PATH. Install it first: winget install Gyan.FFmpeg
  goto :error
)

if not exist "%VENV_DIR%\Scripts\python.exe" (
  echo Creating virtual environment in %VENV_DIR% ...
  %BASE_PYTHON% -m venv "%VENV_DIR%" || goto :error
)

set "PYTHON=%VENV_DIR%\Scripts\python.exe"
"%PYTHON%" -c "import sys; assert (3, 10) <= sys.version_info[:2] < (3, 14) and sys.maxsize > 2**32" >nul 2>nul || (
  echo The existing .venv uses an unsupported Python. Run cleanup_env.bat and try again.
  goto :error
)
if not exist "%SETUP_MARKER%" (
  echo Installing packages into %VENV_DIR% ...
  "%PYTHON%" -m pip install --no-cache-dir torch==2.8.0+cu128 torchvision==0.23.0+cu128 torchaudio==2.8.0+cu128 --index-url https://download.pytorch.org/whl/cu128 || goto :error
  "%PYTHON%" -m pip install --no-cache-dir -r "%REQUIREMENTS_FILE%" || goto :error
  "%PYTHON%" -m pip check || goto :error
) else if /I not "%MOJIOKOSI_SKIP_LIBRARY_UPDATE%"=="1" (
  echo Checking Python libraries for compatible updates ...
  "%PYTHON%" -m pip install --disable-pip-version-check --upgrade --upgrade-strategy only-if-needed -r "%REQUIREMENTS_FILE%"
  if errorlevel 1 echo Library update check failed. Continuing with the installed environment.
)

rem CTranslate2 can discover CUDA/cuDNN DLLs shipped in PyTorch's wheel.
set "PATH=%VENV_DIR%\Lib\site-packages\torch\lib;%PATH%"
"%PYTHON%" -c "import ctranslate2; assert ctranslate2.__version__ == '4.8.1'" >nul 2>nul || (
  echo Installing CTranslate2 4.8.1 ...
  "%PYTHON%" -m pip install --no-cache-dir --upgrade --force-reinstall --no-deps ctranslate2==4.8.1 || goto :error
)
"%PYTHON%" -c "import numpy, whisper; assert numpy.__version__ == '2.2.6'" >nul 2>nul || (
  echo Installing OpenAI Whisper compatibility packages ...
  "%PYTHON%" -m pip install --no-cache-dir --upgrade --force-reinstall --no-deps numpy==2.2.6 openai-whisper==20250625 || goto :error
)
"%PYTHON%" -c "import flask" >nul 2>nul || (
  echo Installing Web UI packages ...
  "%PYTHON%" -m pip install --no-cache-dir -r "%REQUIREMENTS_FILE%" || goto :error
)
"%PYTHON%" -c "import ctranslate2, flask, numpy, torch, torchaudio, torchvision, whisper, whisperx" >nul 2>nul || (
  echo One or more required Python packages cannot be imported. Run cleanup_env.bat and try again.
  goto :error
)
"%PYTHON%" -m pip check || goto :error
if not exist "%SETUP_MARKER%" type nul > "%SETUP_MARKER%" || goto :error
"%PYTHON%" -c "import torch; print('Torch:', torch.__version__); print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'not available (CPU mode can be used)'); print('CUDA:', torch.version.cuda)" || goto :error
if /I "%MOJIOKOSI_CHECK_ONLY%"=="1" (
  echo Environment checks passed.
  goto :end
)
if /I "%MOJIOKOSI_SETUP_ONLY%"=="1" (
  echo Environment setup completed.
  goto :end
)
echo Starting Web UI at http://127.0.0.1:7860 ...
"%PYTHON%" app.py || goto :error
goto :end

:error
set "RUN_RESULT=1"
echo.
echo Could not start the application. Please read README.md.
if /I not "%MOJIOKOSI_NO_PAUSE%"=="1" pause
:end
endlocal & exit /b %RUN_RESULT%

:check_for_updates
where git >nul 2>nul || (
  echo Git was not found. Skipping source update check.
  exit /b 0
)
if not exist "%CD%\.git" (
  echo This folder is not a Git checkout. Skipping source update check.
  exit /b 0
)
git remote get-url origin >nul 2>nul || (
  echo Git remote "origin" is not configured. Skipping source update check.
  exit /b 0
)
git fetch --quiet --prune origin
if errorlevel 1 (
  echo Could not contact GitHub. Starting the installed version.
  exit /b 0
)
set "GIT_UPSTREAM="
for /f "delims=" %%U in ('git rev-parse --abbrev-ref --symbolic-full-name "@{upstream}" 2^>nul') do set "GIT_UPSTREAM=%%U"
if not defined GIT_UPSTREAM (
  set "GIT_BRANCH="
  for /f "delims=" %%B in ('git branch --show-current 2^>nul') do set "GIT_BRANCH=%%B"
  if defined GIT_BRANCH (
    git show-ref --verify --quiet "refs/remotes/origin/!GIT_BRANCH!" && set "GIT_UPSTREAM=origin/!GIT_BRANCH!"
  )
)
if not defined GIT_UPSTREAM (
  echo No upstream branch is configured. Starting the installed version.
  exit /b 0
)
set "REMOTE_COMMITS=0"
for /f "delims=" %%C in ('git rev-list --count HEAD..!GIT_UPSTREAM! 2^>nul') do set "REMOTE_COMMITS=%%C"
if "!REMOTE_COMMITS!"=="0" (
  echo Source code is up to date.
  exit /b 0
)
set "GIT_DIRTY=0"
git diff --quiet --ignore-submodules -- || set "GIT_DIRTY=1"
git diff --cached --quiet --ignore-submodules -- || set "GIT_DIRTY=1"
for /f "delims=" %%F in ('git ls-files --others --exclude-standard 2^>nul') do set "GIT_DIRTY=1"
if "!GIT_DIRTY!"=="1" (
  echo A newer version is available, but local changes were found.
  echo Automatic update was skipped to protect the local files.
  exit /b 0
)
echo !REMOTE_COMMITS! update commit(s) found. Updating source code ...
git pull --ff-only --quiet
if errorlevel 1 (
  echo Automatic source update could not be completed. Starting the installed version.
) else (
  echo Source code update completed.
)
exit /b 0
