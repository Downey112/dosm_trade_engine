from pathlib import Path

import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

RM_MILLION = 1e6
HEADLINE_Z_THRESHOLD = 2.5
SECTOR_Z_THRESHOLD = 3.0

# The OpenDOSM dictionary only describes sections 0-8, but the trade table also reports section 9
SITC_SECTION_9 = {
    "section": "9",
    "desc_en": "Miscellaneous transactions and commodities",
    "desc_bm": "Pelbagai urus niaga dan barangan",
}


def assert_monthly(dates, name):
    # pct_change(12) is only a true year-on-year figure when no month is missing
    expected = pd.date_range(dates.min(), dates.max(), freq="MS")
    if len(dates) != len(expected) or not (dates.values == expected.values).all():
        raise ValueError(f"{name}: dates are not a gap-free monthly series")


def save(df, name):
    df.to_parquet(PROCESSED_DIR / f"{name}.parquet", index=False)
    df.to_csv(PROCESSED_DIR / f"{name}.csv", index=False, date_format="%Y-%m-%d")


def build_fact_headline():
    df = pd.read_parquet(RAW_DIR / "trade_headline.parquet")
    df = df[df["series"] == "abs"].drop(columns="series").copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    assert_monthly(df["date"], "trade_headline")

    # Conversion to RM Millions
    value_cols = [
        "exports",
        "exports_domestic",
        "re_exports",
        "imports",
        "imports_retained",
        "total",
        "balance",
    ]
    df[value_cols] = df[value_cols] / RM_MILLION

    # 12-Month YoY Growth Rates
    df["exports_yoy_pct"] = df["exports"].pct_change(12) * 100
    df["imports_yoy_pct"] = df["imports"].pct_change(12) * 100

    # Rolling Metrics
    df["exports_3m_ma"] = df["exports"].rolling(window=3).mean()
    df["trade_balance_3m_ma"] = df["balance"].rolling(window=3).mean()

    # Z-Score Outlier Flagging on YoY Export Fluctuations
    df["exports_yoy_zscore"] = stats.zscore(df["exports_yoy_pct"], nan_policy="omit")
    df["is_export_anomaly"] = df["exports_yoy_zscore"].abs() > HEADLINE_Z_THRESHOLD

    save(df, "fact_trade_headline")
    print(
        f"[OK] fact_trade_headline: {df.shape[0]} rows, "
        f"{df['is_export_anomaly'].sum()} anomalies flagged"
    )


def build_dim_sitc():
    df_dict = pd.read_parquet(RAW_DIR / "dict_sitc.parquet")

    dim_sitc = df_dict[df_dict["digits"] == 1][["section", "desc_en", "desc_bm"]].copy()
    dim_sitc["section"] = dim_sitc["section"].astype(str)
    dim_sitc = dim_sitc.drop_duplicates(subset="section")
    if SITC_SECTION_9["section"] not in set(dim_sitc["section"]):
        dim_sitc = pd.concat([dim_sitc, pd.DataFrame([SITC_SECTION_9])], ignore_index=True)

    dim_sitc = dim_sitc.sort_values("section").reset_index(drop=True)
    dim_sitc["section_label"] = dim_sitc["section"] + " - " + dim_sitc["desc_en"]

    save(dim_sitc, "dim_sitc")
    print(f"[OK] dim_sitc: {dim_sitc.shape[0]} rows")
    return dim_sitc


def build_fact_sitc(dim_sitc):
    df = pd.read_parquet(RAW_DIR / "trade_sitc_1d.parquet")
    df["date"] = pd.to_datetime(df["date"])
    df["section"] = df["section"].astype(str)

    # "overall" is the sum of sections 0-9; keeping it would double count every total
    df = df[df["section"] != "overall"].copy()

    unknown = set(df["section"]) - set(dim_sitc["section"])
    if unknown:
        raise ValueError(f"trade_sitc_1d: sections missing from dim_sitc: {sorted(unknown)}")

    df = df.sort_values(by=["section", "date"]).reset_index(drop=True)
    for section, dates in df.groupby("section")["date"]:
        assert_monthly(dates.reset_index(drop=True), f"trade_sitc_1d section {section}")

    # Conversion to RM Millions (same unit as fact_trade_headline)
    df[["exports", "imports"]] = df[["exports", "imports"]] / RM_MILLION

    # Derived Metrics
    df["trade_balance"] = df["exports"] - df["imports"]
    df["exports_yoy_pct"] = df.groupby("section")["exports"].pct_change(12) * 100

    # Sector Anomaly Detection on YoY growth, so the long-run trend is not flagged as a spike
    df["exports_yoy_zscore"] = df.groupby("section")["exports_yoy_pct"].transform(
        lambda x: stats.zscore(x, nan_policy="omit")
    )
    df["is_sector_spike"] = df["exports_yoy_zscore"].abs() > SECTOR_Z_THRESHOLD

    save(df, "fact_trade_sitc")
    print(
        f"[OK] fact_trade_sitc: {df.shape[0]} rows, "
        f"{df['is_sector_spike'].sum()} sector spikes flagged"
    )


if __name__ == "__main__":
    build_fact_headline()
    build_fact_sitc(build_dim_sitc())
