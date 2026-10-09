#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

if [ -x .venv/Scripts/python.exe ]; then
    PYTHON=.venv/Scripts/python.exe
elif [ -x .venv/bin/python ]; then
    PYTHON=.venv/bin/python
else
    PYTHON=python
fi

echo "[1/3] Syncing raw endpoints from OpenDOSM..."
"$PYTHON" scripts/01_ingest.py

echo "[2/3] Running statistical transformations & anomaly detection..."
"$PYTHON" scripts/02_transform.py

echo "[3/3] Validating processed outputs..."
"$PYTHON" scripts/03_validate.py

echo "[COMPLETE] Processed files ready in data/processed/"
