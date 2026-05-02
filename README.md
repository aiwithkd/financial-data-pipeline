# Financial Data Pipeline & Quality Monitor

An end-to-end data pipeline for financial datasets - raw CSV ingestion, configurable quality checks, transformation with derived metrics, SQLite storage, and a Streamlit dashboard for monitoring pipeline runs and data quality.

**Live App: [financial-data-pipeline-aiwithkd.streamlit.app](https://financial-data-pipeline-aiwithkd.streamlit.app)**

---

## Background

Most data quality problems in financial ops are caught too late - after a bad file has already been loaded somewhere downstream. The standard fix is to add validation logic directly in the pipeline: check the data before it moves, flag what fails, and load only what passes.

This project builds that workflow for three financial datasets (market prices, portfolio positions, transactions). Each dataset has its own set of quality rules defined in YAML. The pipeline runs the checks, strips out bad rows, transforms the clean data, loads it to SQLite, and records everything so you can see exactly what happened on each run.

---

## Results

| Dataset | Rows Ingested | Rows Passed | Issues Found |
|---|---|---|---|
| Market Prices | 152 | 144 | Null prices, negative prices, bid > ask inversions, bad currency codes, duplicate ISINs |
| Portfolio Positions | 245 | 236 | Null account IDs, zero quantities, negative market values, bad currencies |
| Transactions | 150 | 142 | Null account IDs, invalid transaction types, zero quantities |

All quality issues are seeded intentionally into the sample data to show detection working.

---

## Project Structure

```
financial-data-pipeline/
├── app.py                         # Streamlit entry point
├── requirements.txt
├── config/
│   └── pipeline.yaml              # quality rules per dataset
├── data/
│   └── raw/                       # input CSV files
├── src/
│   ├── models.py                  # PipelineRun, QualityCheck, QualityRule dataclasses
│   ├── database.py                # SQLite: init, insert, fetch
│   ├── ingestion/
│   │   └── loader.py              # CSV reader with encoding detection
│   ├── quality/
│   │   └── engine.py              # runs all quality checks, returns clean df + check results
│   ├── transformation/
│   │   └── transforms.py          # per-dataset transforms + derived columns
│   └── orchestration/
│       ├── config_loader.py       # YAML -> DatasetConfig
│       ├── pipeline.py            # sequences all stages for one dataset
│       └── scheduler.py          # APScheduler wrapper for background runs
└── scripts/
    └── generate_sample_data.py    # generates 3 datasets with seeded quality issues
```

---

## Pipeline Stages

**1. Ingest** - reads the raw CSV, normalises column names to snake_case, handles encoding automatically (UTF-8, UTF-8-BOM, latin-1 fallback).

**2. Quality checks** - runs all rules from `pipeline.yaml` against the raw dataframe. Each check returns a pass/fail result with the expected value, actual value, and number of rows affected. HIGH severity failures mark those rows for exclusion.

**3. Transform** - runs only on clean rows. Coerces numeric columns, standardises strings, parses dates, and adds derived columns.

**4. Load** - inserts clean rows to SQLite. Records the pipeline run metadata and all quality check results so the dashboard can show history.

---

## Quality Check Types

| Type | What it catches |
|---|---|
| `null_check` | Missing values above a threshold |
| `range_check` | Values outside a min/max range |
| `schema_check` | Missing required columns |
| `duplicate_check` | Duplicate key combinations |
| `allowed_values` | Values not in an expected set |
| `cross_field_check` | Inconsistent field relationships (e.g. bid > ask) |
| `row_count_check` | File too small / truncated feed |

Severity: HIGH means the row is excluded from the load. MEDIUM and LOW are flagged but pass through.

---

## Derived Columns After Transform

**Prices:** `spread` (ask - bid), `spread_bps` (spread as basis points of close price)

**Positions:** `mv_recalculated` (quantity * price), `mv_variance_pct` (% gap between reported and recalculated market value - useful for catching stale valuations)

**Transactions:** `settlement_lag_days` (settlement_date - trade_date - flags anything settling same-day or before trade date)

---

## Running Locally

```bash
git clone https://github.com/aiwithkd/financial-data-pipeline
cd financial-data-pipeline
pip install -r requirements.txt
python scripts/generate_sample_data.py
streamlit run app.py
```

Click "Run Now" in the sidebar to trigger the pipeline. The dashboard updates immediately.

---

## Tech Stack

| Tool | Role |
|---|---|
| Python 3.10+ | Core |
| Pandas 2.2+ | Data loading and transformation |
| SQLAlchemy 2.0+ | SQLite writes |
| APScheduler 3.10+ | Background scheduling |
| PyYAML | Quality rule configs |
| Streamlit | Dashboard |
| Plotly | Charts |

---

## Challenges

### 1. Schema drift between raw input and transformed output

The quality engine checks the raw dataframe. The transform layer then adds derived columns (spread, mv_recalculated, settlement_lag_days). When the load step tried to insert into a pre-defined SQLite table, it failed because the derived columns didn't exist in the schema.

Fixed by removing the static CREATE TABLE definitions for processed data tables and letting SQLAlchemy infer the schema from the dataframe on first write. The pipeline_runs and quality_checks tables stay statically defined since their structure is fully controlled.

### 2. Pipeline status conflating execution health with data quality

Early version set `run.status = "FAILED"` whenever a HIGH severity check failed. This meant a healthy pipeline that correctly caught bad data showed up as a failure in the dashboard. Made it impossible to tell "pipeline broke" from "pipeline worked and found bad data".

Changed status to reflect pipeline execution only: SUCCESS means all four stages completed without exceptions. Data quality is tracked separately through the quality_check records. The dashboard shows both independently.

### 3. SQLite write contention with background thread

APScheduler runs jobs in a background thread. SQLite threw `ProgrammingError: SQLite objects created in a thread can only be used in that same thread` when the job tried to write using a connection opened in the main thread.

Fixed by opening a new connection per database call instead of sharing a module-level connection. Each function opens, uses, and closes its own connection via context manager.

### 4. Cross-field checks comparing string-typed columns

The bid/ask check uses `df.eval("bid_price < ask_price")`. On the raw dataframe before transformation, both columns are still strings. Python string comparison made `"100" < "99"` evaluate to True, which produced wrong results without raising any error.

Fixed by coercing numeric columns to float before running any cross-field expression. Also wrapped `df.eval()` in a try/except that catches type errors and returns a FAIL check with the actual error message instead of silently passing.

### 5. Streamlit Cloud losing SQLite data on cold start

Streamlit Cloud has an ephemeral filesystem - the database is gone after inactivity. Landing on an empty dashboard is confusing.

Fixed by calling `db.init_db()` at startup (creates tables if missing), committing the raw CSV files to the repo so the pipeline always has something to process, and designing the dashboard around a single-run view rather than requiring accumulated history to be useful.

---

## What I'd Add Next

- Replace the custom quality engine with Great Expectations, keeping the YAML config as the expectation suite
- dbt models for the transformation layer so transforms are SQL-based and self-documenting
- Parquet output partitioned by date, which makes time-series quality trending much easier
- Alerting on HIGH severity failures so you don't have to check the dashboard manually

---

*[Kunal Deokar](https://github.com/aiwithkd)*
