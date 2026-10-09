import io
import time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

BASE_URL = "https://storage.dosm.gov.my"
ENDPOINTS = {
    "trade_headline": {
        "path": "trade/trade_headline",
        "columns": {"series", "date", "exports", "imports", "total", "balance"},
    },
    "trade_sitc_1d": {
        "path": "trade/trade_sitc_1d",
        "columns": {"date", "section", "exports", "imports"},
    },
    "dict_sitc": {
        "path": "dictionaries/sitc",
        "columns": {"digits", "section", "desc_en", "desc_bm"},
    },
}

MAX_ATTEMPTS = 5
TIMEOUT = 60


def fetch(url):
    # storage.dosm.gov.my resets connections intermittently, so retry with backoff
    last_error = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = requests.get(url, timeout=TIMEOUT)
            response.raise_for_status()
            return response.content
        except requests.RequestException as error:
            last_error = error
            print(f"[RETRY] {url} attempt {attempt}/{MAX_ATTEMPTS}: {error}")
            time.sleep(2 * attempt)
    raise RuntimeError(f"Could not download {url}") from last_error


def load(path):
    try:
        return pd.read_parquet(io.BytesIO(fetch(f"{BASE_URL}/{path}.parquet")))
    except RuntimeError as error:
        print(f"[WARN] parquet unavailable, falling back to CSV: {error}")
        return pd.read_csv(io.BytesIO(fetch(f"{BASE_URL}/{path}.csv")))


def sync_storage():
    for name, spec in ENDPOINTS.items():
        df = load(spec["path"])

        missing = spec["columns"] - set(df.columns)
        if missing:
            raise ValueError(f"{name}: expected columns missing: {sorted(missing)}")
        if df.empty:
            raise ValueError(f"{name}: downloaded table is empty")

        # Write to a temp file first so a failed run never leaves a half-written file
        out_file = RAW_DIR / f"{name}.parquet"
        tmp_file = out_file.with_suffix(".parquet.tmp")
        df.to_parquet(tmp_file, index=False)
        tmp_file.replace(out_file)
        print(f"[OK] {name:<16} -> {out_file.relative_to(ROOT)} ({df.shape[0]} rows)")


if __name__ == "__main__":
    sync_storage()
