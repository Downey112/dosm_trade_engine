@echo off
setlocal
cd /d "%~dp0"

set "PYTHON=.venv\Scripts\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"

echo [1/3] Syncing raw endpoints from OpenDOSM...
"%PYTHON%" scripts\01_ingest.py || exit /b 1

echo [2/3] Running statistical transformations ^& anomaly detection...
"%PYTHON%" scripts\02_transform.py || exit /b 1

echo [3/3] Validating processed outputs...
"%PYTHON%" scripts\03_validate.py || exit /b 1

echo [COMPLETE] Processed files ready in data\processed\
