@echo off
setlocal
cd /d "%~dp0"

set "RUN_ID=%~1"
if "%RUN_ID%"=="" set "RUN_ID=exp_A_capillary_seed0"

set "GRAPH=%~2"
if "%GRAPH%"=="" set "GRAPH=data\HC1.5_gurobi.gml"

set "EXPERIMENTS=%~3"
if "%EXPERIMENTS%"=="" set "EXPERIMENTS=experiments"

if not exist "%GRAPH%" (
    echo Graph file not found: %GRAPH%
    exit /b 1
)

if not exist "%EXPERIMENTS%\%RUN_ID%" (
    echo Experiment run not found: %EXPERIMENTS%\%RUN_ID%
    exit /b 1
)

set "UV_DIR=.tools\uv"
set "UV_EXE=%UV_DIR%\uv.exe"

if not exist "%UV_EXE%" (
    mkdir "%UV_DIR%" 2>nul
    powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $url='https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip'; $zip='.tools\uv\uv.zip'; Invoke-WebRequest -Uri $url -OutFile $zip; Expand-Archive -LiteralPath $zip -DestinationPath '.tools\uv\pkg' -Force; $uv=Get-ChildItem -Path '.tools\uv\pkg' -Filter uv.exe -Recurse | Select-Object -First 1; if (-not $uv) { throw 'uv.exe not found in archive' }; Copy-Item -LiteralPath $uv.FullName -Destination '.tools\uv\uv.exe' -Force"
    if errorlevel 1 exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    "%UV_EXE%" venv --python 3.11 .venv
    if errorlevel 1 exit /b 1
)

"%UV_EXE%" pip install --python ".venv\Scripts\python.exe" -r requirements.txt
if errorlevel 1 exit /b 1

"%UV_EXE%" pip install --python ".venv\Scripts\python.exe" "napari[all]"
if errorlevel 1 exit /b 1

".venv\Scripts\python.exe" src\visualize.py "%RUN_ID%" --graph "%GRAPH%" --experiments "%EXPERIMENTS%"
