@echo off
setlocal EnableExtensions
cd /d "%~dp0"

rem Keep the complete Python environment inside this project folder.
set "VENV_DIR=%CD%\.venv"
set "SETUP_MARKER=%VENV_DIR%\.setup_complete_cuda128_v2"
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
%PYTHON% -c "import sys; assert (3, 10) <= sys.version_info[:2] < (3, 14) and sys.maxsize > 2**32" >nul 2>nul || (
  echo The existing .venv uses an unsupported Python. Run cleanup_env.bat and try again.
  goto :error
)
if not exist "%SETUP_MARKER%" (
  echo Installing packages into %VENV_DIR% ...
  %PYTHON% -m pip install --no-cache-dir torch==2.8.0+cu128 torchvision==0.23.0+cu128 torchaudio==2.8.0+cu128 --index-url https://download.pytorch.org/whl/cu128 || goto :error
  %PYTHON% -m pip install --no-cache-dir -r requirements.txt || goto :error
  %PYTHON% -m pip check || goto :error
  type nul > "%SETUP_MARKER%"
)

rem CTranslate2 can discover CUDA/cuDNN DLLs shipped in PyTorch's wheel.
set "PATH=%VENV_DIR%\Lib\site-packages\torch\lib;%PATH%"
%PYTHON% -c "import ctranslate2; assert ctranslate2.__version__ == '4.8.1'" >nul 2>nul || (
  echo Installing CTranslate2 4.8.1 ...
  %PYTHON% -m pip install --no-cache-dir --upgrade --force-reinstall --no-deps ctranslate2==4.8.1 || goto :error
)
%PYTHON% -c "import numpy, whisper; assert numpy.__version__ == '2.2.6'" >nul 2>nul || (
  echo Installing OpenAI Whisper compatibility packages ...
  %PYTHON% -m pip install --no-cache-dir --upgrade --force-reinstall --no-deps numpy==2.2.6 openai-whisper==20250625 || goto :error
)
%PYTHON% -c "import flask" >nul 2>nul || (
  echo Installing Web UI packages ...
  %PYTHON% -m pip install --no-cache-dir -r requirements.txt || goto :error
)
%PYTHON% -c "import torch; print('Torch:', torch.__version__); print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'not available (CPU mode can be used)'); print('CUDA:', torch.version.cuda)" || goto :error
if /I "%MOJIOKOSI_CHECK_ONLY%"=="1" (
  echo Environment checks passed.
  goto :end
)
if /I "%MOJIOKOSI_SETUP_ONLY%"=="1" (
  echo Environment setup completed.
  goto :end
)
echo Starting Web UI at http://127.0.0.1:7860 ...
%PYTHON% app.py || goto :error
goto :end

:error
set "RUN_RESULT=1"
echo.
echo Could not start the application. Please read README.md.
if /I not "%MOJIOKOSI_NO_PAUSE%"=="1" pause
:end
endlocal & exit /b %RUN_RESULT%
