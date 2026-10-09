import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = ROOT / "data" / "processed"

# Sections should add up to the headline figure; larger gaps are reported, not hidden
RECONCILE_TOLERANCE_PCT = 1.0

failures = []


def check(condition, message):
    print(f"[{'PASS' if condition else 'FAIL'}] {message}")
    if not condition:
        failures.append(message)


def validate():
    headline = pd.read_parquet(PROCESSED_DIR / "fact_trade_headline.parquet")
    sitc = pd.read_parquet(PROCESSED_DIR / "fact_trade_sitc.parquet")
    dim = pd.read_parquet(PROCESSED_DIR / "dim_sitc.parquet")

    check(headline["date"].is_unique, "fact_trade_headline: one row per month")
    check(
        not sitc.duplicated(["date", "section"]).any(),
        "fact_trade_sitc: one row per month and section",
    )
    check(dim["section"].is_unique, "dim_sitc: section is a unique key")
    check(
        set(sitc["section"]) <= set(dim["section"]),
        "fact_trade_sitc: every section exists in dim_sitc",
    )
    check("overall" not in set(sitc["section"]), "fact_trade_sitc: no 'overall' rows")
    check(
        headline[["exports", "imports", "balance"]].notna().all().all(),
        "fact_trade_headline: no missing exports/imports/balance",
    )
    check(
        ((headline["exports"] - headline["imports"] - headline["balance"]).abs() < 1e-6).all(),
        "fact_trade_headline: balance = exports - imports",
    )
    check(
        sitc[["exports", "imports"]].notna().all().all(),
        "fact_trade_sitc: no missing exports/imports",
    )

    for name in ("fact_trade_headline", "fact_trade_sitc", "dim_sitc"):
        rows_parquet = len(pd.read_parquet(PROCESSED_DIR / f"{name}.parquet"))
        rows_csv = len(pd.read_csv(PROCESSED_DIR / f"{name}.csv"))
        check(rows_parquet == rows_csv, f"{name}: CSV and parquet row counts match")

    # Reconcile sector totals against the headline table
    sector_total = sitc.groupby("date")[["exports", "imports"]].sum()
    reference = headline.set_index("date")[["exports", "imports"]]
    gap_pct = ((sector_total - reference) / reference * 100).dropna()
    off = gap_pct[(gap_pct.abs() > RECONCILE_TOLERANCE_PCT).any(axis=1)]
    if off.empty:
        print(f"[PASS] sector totals within {RECONCILE_TOLERANCE_PCT}% of headline every month")
    else:
        print(
            f"[WARN] sector totals differ from headline by more than "
            f"{RECONCILE_TOLERANCE_PCT}% in {len(off)} month(s) (source revisions):"
        )
        print(off.round(2).to_string())

    print(
        f"[INFO] headline {headline['date'].min():%Y-%m} to {headline['date'].max():%Y-%m}, "
        f"sitc {sitc['date'].min():%Y-%m} to {sitc['date'].max():%Y-%m}"
    )

    if failures:
        print(f"[FAILED] {len(failures)} check(s) failed")
        sys.exit(1)
    print("[OK] all checks passed")


if __name__ == "__main__":
    validate()
