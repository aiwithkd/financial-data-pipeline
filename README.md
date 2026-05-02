# Financial Data Pipeline & Quality Monitor

Production-inspired data pipeline for financial datasets — configurable quality rules, multi-stage processing (ingest → validate → transform → load), SQLite persistence, and a live Streamlit monitoring dashboard with run history, quality scores, and data explorer.

**Live App → [financial-data-pipeline-aiwithkd.streamlit.app](https://financial-data-pipeline-aiwithkd.streamlit.app)**

---

## What This Project Does and Why

Every financial operations team runs daily data pipelines — ingest a file from a vendor or system, validate it meets quality standards, transform it into a clean analytical format, and load it to a downstream store. When something fails, the team needs to know immediately: which dataset, which check, how many rows affected, and how severe.

This project builds a complete, reusable financial data pipeline that handles the full workflow: load three financial datasets (market prices, portfolio positions, transactions), run configurable quality checks per dataset, transform the data with derived metrics, load clean records to a SQLite database, and surface everything on a monitoring dashboard with run history, quality scores, and a data explorer.

Directly modelled on data quality work done in financial data operations — the check types, severity tiers, and monitoring concepts mirror production-grade tooling used in wealth management and fintech environments.

---

## Results at a Glance

| Dataset | Rows Ingested | Rows Passed | Quality Issues Detected |
|---|---|---|---|
| Market Prices | 152 | 144 | Null prices, negative prices, bid > ask inversions, invalid currency, duplicates |
| Portfolio Positions | 245 | 236 | Null account IDs, zero quantities, negative market values, invalid currencies |
| Transactions | 150 | 142 | Null account IDs, invalid transaction types, zero quantities |

Quality issues are intentionally injected to demonstrate the detection capability — this is how you'd use the pipeline to catch real upstream data problems before they reach production.

---

## Repository Structure

```
financial-data-pipeline/
├── app.py                          # Streamlit entry point
├── requirements.txt                # Dependencies
├── pyproject.toml                  # Build config
├── .streamlit/
│   └── config.toml                 # Dark theme
│
├── config/
│   └── pipeline.yaml               # Quality rules per dataset (config-driven)
│
├── data/
│   └── raw/                        # Input CSV files (prices, positions, transactions)
│
├── src/
│   ├── models.py                   # Domain dataclasses: PipelineRun, QualityCheck, QualityRule
│   ├── database.py                 # SQLite layer — init, insert, fetch for all tables
│   ├── ingestion/
│   │   └── loader.py               # CSV ingestion with encoding detection, column normalisation
│   ├── quality/
│   │   └── engine.py               # Quality check engine: null, range, schema, cross-field, duplicate
│   ├── transformation/
│   │   └── transforms.py           # Per-dataset transforms: type coercion, derived metrics
│   ├── orchestration/
│   │   ├── config_loader.py        # YAML config → DatasetConfig + QualityRule dataclasses
│   │   ├── pipeline.py             # Pipeline orchestrator: sequences all stages per dataset
│   │   └── scheduler.py           # APScheduler wrapper: background interval scheduling
│   └── reporting/
│
└── scripts/
    └── generate_sample_data.py     # Generates 3 datasets with seeded quality issues
```

---

## Architecture

```
┌─────────────────────────────────────────────┐
│            STREAMLIT DASHBOARD               │
│  Run History | Quality Scores | Data Explorer│
└──────────────────────┬──────────────────────┘
                       │  Trigger / Read
┌──────────────────────▼──────────────────────┐
│              ORCHESTRATION LAYER             │
│  pipeline.py — sequences all stages          │
│  scheduler.py — APScheduler interval runs    │
│  config_loader.py — YAML → DatasetConfig     │
└──────────────────────┬──────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
┌──────────────┐ ┌──────────┐ ┌────────────┐
│  INGESTION   │ │ QUALITY  │ │ TRANSFORM  │
│  loader.py   │ │ engine.py│ │ transforms │
│  CSV → DF    │ │ 7 check  │ │ coerce +   │
│              │ │ types    │ │ derive     │
└──────────────┘ └──────────┘ └────────────┘
                       │
┌──────────────────────▼──────────────────────┐
│               DATABASE LAYER                 │
│  SQLite — pipeline_runs, quality_checks,     │
│  processed_prices/positions/transactions     │
└─────────────────────────────────────────────┘
```

**Key design decisions:**

**Config-driven quality rules:** Every check — which column, what threshold, what severity — lives in `config/pipeline.yaml`. Adding a new dataset or changing a threshold requires zero code changes, only a YAML edit. This mirrors how tools like Great Expectations are configured in production.

**Seven check types:** `null_check`, `range_check`, `schema_check`, `duplicate_check`, `allowed_values`, `cross_field_check`, `row_count_check`. Each maps directly to a real data quality concern (e.g. cross_field covers bid > ask inversions, a real market data quality issue).

**Clean rows pass, bad rows are counted:** The pipeline separates clean rows (passed all HIGH severity checks) from bad rows, loads only clean data, and records exactly how many rows failed each check. This is the standard pattern in production ETL — fail fast, quarantine bad data, don't pollute the output.

**Strict layer separation:** The quality engine never imports Streamlit. The dashboard never calls the quality engine directly — it reads from the database. Layers are independently testable.

---

## Quality Check Types

| Check Type | What It Catches | Example |
|---|---|---|
| `null_check` | Missing values above threshold | `close_price` null in 3% of rows |
| `range_check` | Values outside valid range | Negative prices, zero quantities |
| `schema_check` | Missing required columns | Feed missing `settlement_date` column |
| `duplicate_check` | Duplicate key combinations | Same ISIN appearing twice on same date |
| `allowed_values` | Values not in expected set | Currency = "XXX" instead of USD/GBP/EUR |
| `cross_field_check` | Inconsistent field relationships | `bid_price > ask_price` — price inversion |
| `row_count_check` | File too small — truncated feed | Prices file has only 5 rows |

Severity levels: **HIGH** (row excluded from load), **MEDIUM** (flagged but row passes), **LOW** (warning only).

---

## Derived Metrics After Transform

Each dataset gets additional computed columns after transformation:

**Prices:** `spread` (ask − bid), `spread_bps` (spread as basis points of close price)

**Positions:** `mv_recalculated` (quantity × price), `mv_variance_pct` (% difference between reported and recalculated market value — catches stale valuations)

**Transactions:** `settlement_lag_days` (settlement_date − trade_date — flags same-day or pre-date settlements)

---

## Step-by-Step Pipeline

### Step 1 — Ingest (`src/ingestion/loader.py`)
Reads CSV with automatic encoding detection (UTF-8 → UTF-8-BOM → latin-1). Normalises column names to `snake_case`, strips whitespace, drops unnamed columns.

### Step 2 — Quality Checks (`src/quality/engine.py`)
Runs all configured rules against the raw DataFrame. Each check returns a `QualityCheck` record with status (PASS/FAIL/WARN), expected vs actual, and rows affected. HIGH severity failures mark rows for exclusion.

### Step 3 — Transform (`src/transformation/transforms.py`)
Coerces numeric columns, standardises string fields (uppercase currencies, title-case asset classes), parses dates, and computes derived metrics. Only runs on clean rows.

### Step 4 — Load (`src/database.py`)
Inserts clean transformed rows to SQLite. Writes `pipeline_run` metadata and all `quality_check` records. The dashboard reads directly from these tables.

---

## Running Locally

```bash
git clone https://github.com/aiwithkd/financial-data-pipeline
cd financial-data-pipeline
pip install -r requirements.txt

# Generate sample data
python scripts/generate_sample_data.py

# Run the app
streamlit run app.py
# open http://localhost:8501
```

Click **▶ Run Now** in the sidebar to trigger the pipeline. The dashboard updates immediately.

---

## Tech Stack

| Tool | Version | Role |
|---|---|---|
| Python | 3.10+ | Core runtime |
| Pandas | 2.2+ | Data loading, transformation, aggregation |
| NumPy | 1.26+ | Vectorised operations |
| SQLAlchemy | 2.0+ | ORM-free SQLite interface for bulk inserts |
| APScheduler | 3.10+ | Background interval scheduling |
| PyYAML | 6.0+ | Config-driven quality rules |
| Streamlit | 1.37+ | Monitoring dashboard |
| Plotly | 5.23+ | Run history bars, quality gauge |

---

## Challenges Faced During Implementation

### 1. Schema drift between raw input and transformed output

**Problem:** The quality engine runs checks on raw DataFrames, then the transformation layer adds derived columns (`spread`, `mv_recalculated`, `settlement_lag_days`). When the load step tried to append to a pre-defined SQLite table schema, it failed with `OperationalError: table has no column` for the new derived fields.

**Resolution:** Removed the static `CREATE TABLE` definitions for processed data tables. SQLAlchemy's `df.to_sql(if_exists="append")` handles schema inference dynamically. The pipeline table (run metadata) and quality checks table remain statically defined because their schema is fully controlled — only the output data tables flex with the transform layer.

---

### 2. Pipeline status conflating pipeline health with data quality

**Problem:** Early versions set `run.status = "FAILED"` whenever any HIGH severity quality check failed. This meant a healthy pipeline that correctly detected bad data appeared as a pipeline failure in the monitoring dashboard — making it impossible to distinguish "the pipeline broke" from "the data is bad, which is expected."

**Resolution:** Status now reflects pipeline execution health only: `SUCCESS` means all four stages completed without exceptions. Data quality is reported separately through `quality_check` records. The dashboard surfaces both independently — a green run with red quality checks is the correct signal for "pipeline worked, data has issues."

---

### 3. SQLite write contention with APScheduler background jobs

**Problem:** APScheduler runs pipeline jobs in a background thread. SQLite's default connection mode throws `ProgrammingError: SQLite objects created in a thread can only be used in that same thread` when the background job tries to write to a connection opened in the main thread.

**Resolution:** Changed `get_conn()` to open a new connection per call (`sqlite3.connect(DB_PATH)`) rather than a module-level shared connection. Each write operation opens, uses, and closes its own connection via context manager. SQLite handles concurrent writes via file locking — safe for the single-writer pattern this pipeline uses.

---

### 4. Cross-field quality checks failing on transformed column names

**Problem:** The `cross_field_check` for bid/ask spread uses `df.eval("bid_price < ask_price")`. After the transformation step renames or coerces columns, the expression works. But running the check on the raw DataFrame before transformation sometimes hit columns that were still string-typed, causing `eval` to do string comparison instead of numeric (`"100" < "99"` is `True` lexicographically).

**Resolution:** The quality engine now coerces numeric columns to `float` via `pd.to_numeric(errors="coerce")` before running cross-field expressions. Added a try/except around `df.eval()` that catches type errors and surfaces them as FAIL checks with a descriptive error message, rather than silently producing wrong results.

---

### 5. Streamlit Cloud ephemeral filesystem losing the SQLite database between sessions

**Problem:** Streamlit Cloud's filesystem is ephemeral — the `pipeline.db` SQLite file is recreated fresh on each cold start. Users landing on the app after an inactivity period would see an empty dashboard with no run history.

**Resolution:** The app calls `db.init_db()` at startup (creates tables if not present) and immediately prompts the user to run the pipeline via the sidebar. The raw CSV data files are committed to the repo, so the pipeline always has data to process. The dashboard is designed to be useful after a single run — the pattern is "run once, see everything" rather than requiring historical accumulation.

---

## Future Scope

- **dbt integration** — replace the custom transform layer with dbt models for SQL-based transformations with built-in testing and documentation generation
- **Great Expectations backend** — swap the custom quality engine for Great Expectations, keeping the YAML config as the expectation suite definition
- **Delta / Parquet output** — write processed data to Parquet files partitioned by date and dataset, enabling time-series quality trending without a database
- **Alerting** — connect failed HIGH severity checks to a notification channel (Slack, email) so operations teams are paged without checking the dashboard manually
- **Multi-source pipeline** — extend to compare two versions of the same dataset (e.g. vendor feed vs internal library) by composing this pipeline with the reconciliation engine

---

*Built by [Kunal Deokar](https://github.com/aiwithkd)*
