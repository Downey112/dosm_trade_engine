# DOSM Trade Engine

Monthly Malaysian trade statistics from [OpenDOSM](https://open.dosm.gov.my), cleaned and
flagged for anomalies in Python, then modelled and visualised in Power BI.

## Run the pipeline

```
run_pipeline.bat        (Windows)
./run_pipeline.sh       (Git Bash / Linux / macOS)
```

First-time setup, if `.venv` does not exist yet:

```
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

| Step | Script | What it does |
|---|---|---|
| 1 | `scripts/01_ingest.py` | Downloads the three OpenDOSM tables to `data/raw/`, with retries and a column check |
| 2 | `scripts/02_transform.py` | Builds the fact and dimension tables in `data/processed/` (parquet + CSV) |
| 3 | `scripts/03_validate.py` | Checks keys, gaps and totals; exits non-zero if a check fails |

## Processed tables

All values are in **RM million**.

- `fact_trade_headline` — one row per month: exports, imports, balance, YoY %, 3-month
  moving averages, and `is_export_anomaly` (|z-score of exports YoY %| > 2.5).
- `fact_trade_sitc` — one row per month and SITC section (0-9): exports, imports, trade
  balance, YoY %, and `is_sector_spike` (|z-score of the section's exports YoY %| > 3).
- `dim_sitc` — the ten SITC sections with English and Malay descriptions.

## Power BI

Open `powerbi/DosmTrade.pbip` in Power BI Desktop and click **Refresh**. The model
(star schema, date table, measures) and the *Trade Overview* page are already built.

The model reads the CSVs from the folder in the `ProcessedFolder` parameter. If the project
is moved, update it under **Transform data > Edit parameters**.

After each pipeline run, click **Refresh** in Power BI to pick up the new month.

## Things to know about the source data

- The SITC table contains an `overall` row per month; the transform drops it so sector
  totals are not double counted.
- The OpenDOSM dictionary describes sections 0-8 only. Section 9 exists in the trade data,
  so the transform adds its description.
- The headline table has been revised for 2024 onwards and the SITC table has not, so
  sector totals differ slightly from the headline figure in those months. The gap is under
  1% except for imports in June and July 2024 (about 10% and 16%). The validation step
  reports these months on every run.
- The SITC table is usually published one month behind the headline table.
