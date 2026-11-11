@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

rem Enable the locally installed ObusSQL preview; set 0 explicitly to disable it.
if not defined MOJIOKOSI_OBUSSQL_ENABLED (
  set "MOJIOKOSI_OBUSSQL_DEFAULTED=1"
  set "MOJIOKOSI_OBUSSQL_ENABLED=1"
)

rem 開発版のMAF接続を有効にする。0を指定すると従来の分析実行を使う。
if not defined MOJIOKOSI_MAF_DEV_ENABLED (
  set "MOJIOKOSI_MAF_DEV_DEFAULTED=1"
  set "MOJIOKOSI_MAF_DEV_ENABLED=1"
  if /I "%MOJIOKOSI_OBUSSQL_ENABLED%"=="0" set "MOJIOKOSI_MAF_DEV_ENABLED=0"
)

rem Keep this block together: Git may replace run.bat while the launcher runs.
if /I not "%MOJIOKOSI_LAUNCH_WORKER%"=="1" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\run_launcher.ps1"
  set "RUN_RESULT=!ERRORLEVEL!"
  if not "!RUN_RESULT!"=="0" (
    echo.
    echo Startup failed. Review the error above and the startup log shown above.
    if /I not "%MOJIOKOSI_NO_PAUSE%"=="1" pause
  )
  exit /b !RUN_RESULT!
)

rem Keep the complete Python environment inside this project folder.
set "VENV_DIR=%CD%\.venv"
set "REQUIREMENTS_FILE=%CD%\config\requirements.txt"
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

if not exist "%VENV_DIR%\Scripts\python.exe" (
  echo Creating virtual environment in %VENV_DIR% ...
  %BASE_PYTHON% -m venv "%VENV_DIR%" || goto :error
)

set "PYTHON=%VENV_DIR%\Scripts\python.exe"
"%PYTHON%" -c "import sys; assert (3, 10) <= sys.version_info[:2] < (3, 14) and sys.maxsize > 2**32" || (
  echo The existing .venv uses an unsupported Python. Run scripts\cleanup_env.bat and try again.
  goto :error
)
set "WINDOWS_CONSTRAINTS="
"%PYTHON%" -c "import sys; assert sys.version_info[:2] == (3, 12)" >nul 2>nul && if exist "%CD%\config\constraints-windows-cp312.txt" set "WINDOWS_CONSTRAINTS=%CD%\config\constraints-windows-cp312.txt"
if not exist "%SETUP_MARKER%" (
  echo Installing packages into %VENV_DIR% ...
  "%PYTHON%" -m pip install --no-cache-dir torch==2.8.0+cu128 torchvision==0.23.0+cu128 torchaudio==2.8.0+cu128 --index-url https://download.pytorch.org/whl/cu128 || goto :error
  call :install_requirements fresh || goto :error
  "%PYTHON%" -m pip check || goto :error
) else if /I not "%MOJIOKOSI_SKIP_LIBRARY_UPDATE%"=="1" (
  echo Checking Python libraries for compatible updates ...
  call :install_requirements update
  if errorlevel 1 echo Library update check failed. Continuing with the installed environment.
)

rem 開発版MAFの固定依存を確認する。分析処理は既存の台帳と停止制御を使う。
if /I "!MOJIOKOSI_MAF_DEV_ENABLED!"=="1" (
  "%PYTHON%" -c "import sys; assert sys.version_info[:2] == (3, 12)" >nul 2>nul
  if errorlevel 1 (
    if not "!MOJIOKOSI_MAF_DEV_DEFAULTED!"=="1" (
      echo MAF development analysis requires Python 3.12. Set MOJIOKOSI_MAF_DEV_ENABLED=0 to use the standard driver.
      goto :error
    )
    echo Warning: MAF development analysis requires Python 3.12; using the standard driver.
    set "MOJIOKOSI_MAF_DEV_ENABLED=0"
  )
)
if /I "!MOJIOKOSI_MAF_DEV_ENABLED!"=="1" (
  "%PYTHON%" -c "from importlib.metadata import version; import agent_framework; assert version('agent-framework-core') == '1.22.0'" >nul 2>nul || (
    "%PYTHON%" -m pip install -r "%CD%\config\requirements-gurumoji-maf-dev.txt"
    if errorlevel 1 (
      if not "!MOJIOKOSI_MAF_DEV_DEFAULTED!"=="1" goto :error
      echo Warning: MAF development dependencies could not be installed; using the standard driver.
      set "MOJIOKOSI_MAF_DEV_ENABLED=0"
    )
  )
)
if /I "!MOJIOKOSI_OBUSSQL_ENABLED!"=="1" (
  call :check_metric_codec
  if errorlevel 1 (
    "%PYTHON%" -c "import sys; assert sys.version_info[:2] >= (3, 12)" >nul 2>nul
    if not errorlevel 1 call :install_metric_codec
    call :check_metric_codec
    if errorlevel 1 (
      if "!MOJIOKOSI_OBUSSQL_DEFAULTED!"=="1" (
        if "!MOJIOKOSI_MAF_DEV_ENABLED!"=="1" if not "!MOJIOKOSI_MAF_DEV_DEFAULTED!"=="1" (
          echo MAF development analysis requires ObusSQL with the metric codec.
          goto :error
        )
        echo Warning: metric codec unavailable; disabling ObusSQL and MAF development analysis.
        set "MOJIOKOSI_OBUSSQL_ENABLED=0"
        set "MOJIOKOSI_MAF_DEV_ENABLED=0"
      ) else (
        echo Warning: metric codec unavailable; new analyses will stop at the pre-check until it is installed.
      )
    )
  )
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
echo Checking required Python package imports ...
"%PYTHON%" -c "import ctranslate2, flask, numpy, torch, torchaudio, torchvision, whisper, whisperx" || (
  echo One or more required Python packages cannot be imported. Run scripts\cleanup_env.bat and try again.
  goto :error
)
"%PYTHON%" -m pip check || goto :error
if not exist "%SETUP_MARKER%" type nul > "%SETUP_MARKER%" || goto :error

rem imageio-ffmpeg ships a Windows ffmpeg executable with the Python package.
rem Copy it to the venv Scripts folder under the conventional name so every
rem child process (including Whisper and the Web UI) can resolve "ffmpeg".
set "PROJECT_FFMPEG=%VENV_DIR%\Scripts\ffmpeg.exe"
if not exist "%PROJECT_FFMPEG%" (
  echo Installing project-local FFmpeg ...
  set "PACKAGED_FFMPEG="
  rem Do not use FOR /F command substitution here.  CMD misparses a quoted
  rem executable path in that context on some Windows installations.
  set "FFMPEG_PATH_FILE=%VENV_DIR%\.imageio-ffmpeg-path.txt"
  "%PYTHON%" -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())" > "!FFMPEG_PATH_FILE!" || goto :error
  set /p "PACKAGED_FFMPEG=" < "!FFMPEG_PATH_FILE!"
  del /q "!FFMPEG_PATH_FILE!" >nul 2>nul
  if not defined PACKAGED_FFMPEG (
    echo Could not obtain the FFmpeg executable from imageio-ffmpeg.
    goto :error
  )
  if not exist "!PACKAGED_FFMPEG!" (
    echo The packaged FFmpeg executable was not found: !PACKAGED_FFMPEG!
    goto :error
  )
  copy /y "!PACKAGED_FFMPEG!" "%PROJECT_FFMPEG%" >nul || goto :error
)
set "PATH=%VENV_DIR%\Scripts;%VENV_DIR%\Lib\site-packages\torch\lib;%PATH%"
where ffmpeg >nul 2>nul || (
  echo Project-local FFmpeg could not be added to PATH.
  goto :error
)
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
set "PYTHONPATH=%CD%\src;%PYTHONPATH%"
"%PYTHON%" -u -m gurumoji.app || goto :error
goto :end

:check_metric_codec
"%PYTHON%" -c "from importlib.metadata import version; from obusql_agent.metric_codec import MetricEncoder, MetricDecoder; assert version('obusql-agent') == '0.1.0'" >nul 2>nul
exit /b %ERRORLEVEL%

:install_metric_codec
setlocal
set "GIT_TERMINAL_PROMPT=0"
set "GCM_INTERACTIVE=never"
"%PYTHON%" -m pip install -r "%CD%\config\requirements-obussql-metric.txt"
endlocal & exit /b %ERRORLEVEL%


:install_requirements
set "INSTALL_OPTIONS=--no-cache-dir"
if /I "%~1"=="update" set "INSTALL_OPTIONS=--disable-pip-version-check --upgrade --upgrade-strategy only-if-needed"
if defined WINDOWS_CONSTRAINTS (
  "%PYTHON%" -m pip install !INSTALL_OPTIONS! -r "%REQUIREMENTS_FILE%" -c "!WINDOWS_CONSTRAINTS!"
  if not errorlevel 1 exit /b 0
  echo Warning: Windows constraints failed; retrying without constraints.
)
"%PYTHON%" -m pip install !INSTALL_OPTIONS! -r "%REQUIREMENTS_FILE%"
exit /b !ERRORLEVEL!


:error
set "RUN_RESULT=%ERRORLEVEL%"
if "%RUN_RESULT%"=="0" set "RUN_RESULT=1"
echo.
echo Could not start the application. Please read README.md.
if /I not "%MOJIOKOSI_NO_PAUSE%"=="1" pause
:end
endlocal & exit /b %RUN_RESULT%
