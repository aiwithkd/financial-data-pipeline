from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st
from datetime import datetime

from src import database as db
from src.orchestration.config_loader import load_config
from src.orchestration.pipeline import run_pipeline, run_all_pipelines

# Init
db.init_db()

st.set_page_config(
    page_title="Financial Data Pipeline",
    page_icon="🔁",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
[data-testid="stMetricValue"] { font-size: 1.5rem; font-weight: 700; }
.block-container { padding-top: 1.5rem; }
div[data-testid="column"] { padding: 0 0.3rem; }
.stAlert { border-radius: 8px; }
</style>
""", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.image("https://img.icons8.com/color/96/data-transfer.png", width=52)
    st.title("Data Pipeline")
    st.caption("Financial Data Pipeline & Quality Monitor")
    st.divider()

    configs = load_config()

    st.markdown("**Datasets**")
    for name, cfg in configs.items():
        raw_exists = (ROOT / cfg.raw_file).exists()
        icon = "🟢" if raw_exists else "🔴"
        st.markdown(f"{icon} {cfg.display_name}")

    st.divider()

    st.markdown("**Run Pipeline**")
    run_target = st.selectbox(
        "Select dataset",
        ["All datasets"] + [cfg.display_name for cfg in configs.values()],
        label_visibility="collapsed",
    )

    if st.button("▶ Run Now", type="primary", use_container_width=True):
        name_map = {cfg.display_name: name for name, cfg in configs.items()}
        with st.spinner("Running pipeline..."):
            if run_target == "All datasets":
                runs = run_all_pipelines(configs)
                success = sum(1 for r in runs if r.status == "SUCCESS")
                st.success(f"{success}/{len(runs)} pipelines completed.")
            else:
                dataset_name = name_map[run_target]
                run = run_pipeline(dataset_name, configs[dataset_name])
                if run.status == "SUCCESS":
                    st.success(f"Pipeline completed — {run.rows_ingested:,} rows ingested.")
                else:
                    st.error(f"Pipeline failed: {run.error_message}")
        st.rerun()

    st.divider()
    if st.button("🔄 Refresh Dashboard", use_container_width=True):
        st.rerun()


# Main
st.title("🔁 Financial Data Pipeline Monitor")
st.caption("End-to-end pipeline: ingest → validate → transform → load. Track quality scores, run history, and data health in real time.")
st.divider()

# Summary KPIs
runs = db.fetch_runs(limit=200)
checks = db.fetch_checks(limit=1000)

total_runs = len(runs)
success_runs = sum(1 for r in runs if r["status"] == "SUCCESS")
failed_runs = sum(1 for r in runs if r["status"] == "FAILED")
total_rows = sum(r["rows_ingested"] for r in runs)
total_checks = len(checks)
passed_checks = sum(1 for c in checks if c["status"] == "PASS")
quality_score = round(passed_checks / total_checks * 100, 1) if total_checks > 0 else 0

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Total Runs", f"{total_runs:,}")
c2.metric("Success Rate", f"{round(success_runs/total_runs*100,1) if total_runs else 0}%")
c3.metric("Failed Runs", f"{failed_runs:,}", delta="↑" if failed_runs > 0 else None, delta_color="inverse")
c4.metric("Rows Processed", f"{total_rows:,}")
c5.metric("Quality Checks Run", f"{total_checks:,}")
c6.metric("Overall Quality Score", f"{quality_score}%")

st.divider()

if total_runs == 0:
    st.info("No pipeline runs yet. Click **▶ Run Now** in the sidebar to start the pipeline.")
    st.stop()

# Quality score by dataset
chart_col, gauge_col = st.columns([3, 2], gap="large")

with chart_col:
    st.subheader("Pipeline Run History")
    runs_df = pd.DataFrame(runs)
    runs_df["started_at"] = pd.to_datetime(runs_df["started_at"])
    runs_df["run_label"] = runs_df["run_id"] + " — " + runs_df["dataset"]
    runs_df["color"] = runs_df["status"].map({"SUCCESS": "#2ecc71", "FAILED": "#e74c3c", "RUNNING": "#f39c12"})

    fig = go.Figure()
    for status, color in [("SUCCESS", "#2ecc71"), ("FAILED", "#e74c3c")]:
        sub = runs_df[runs_df["status"] == status]
        if not sub.empty:
            fig.add_trace(go.Bar(
                x=sub["started_at"],
                y=sub["rows_ingested"],
                name=status,
                marker_color=color,
                hovertemplate="<b>%{customdata}</b><br>Rows: %{y:,}<extra></extra>",
                customdata=sub["dataset"],
            ))
    fig.update_layout(
        height=280, barmode="stack",
        margin=dict(t=10, b=20, l=20, r=20),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", y=1.1),
        xaxis_title="", yaxis_title="Rows Ingested",
        yaxis=dict(gridcolor="#2a2a2a"),
    )
    st.plotly_chart(fig, use_container_width=True)

with gauge_col:
    st.subheader("Quality Score")

    fig_gauge = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=quality_score,
        delta={"reference": 90, "valueformat": ".1f"},
        number={"suffix": "%", "font": {"size": 36}},
        gauge={
            "axis": {"range": [0, 100], "tickwidth": 1},
            "bar": {"color": "#2f81f7"},
            "steps": [
                {"range": [0, 60], "color": "#2d1b1b"},
                {"range": [60, 80], "color": "#2d2616"},
                {"range": [80, 100], "color": "#1b2d1e"},
            ],
            "threshold": {
                "line": {"color": "#2ecc71", "width": 3},
                "thickness": 0.75,
                "value": 90,
            },
        },
    ))
    fig_gauge.update_layout(
        height=280,
        margin=dict(t=20, b=20, l=30, r=30),
        paper_bgcolor="rgba(0,0,0,0)",
        font={"color": "#e6edf3"},
    )
    st.plotly_chart(fig_gauge, use_container_width=True)

st.divider()

# Per-dataset quality breakdown
st.subheader("Quality Checks by Dataset")

checks_df = pd.DataFrame(checks) if checks else pd.DataFrame()

if not checks_df.empty:
    dataset_quality = (
        checks_df.groupby(["dataset", "status"])
        .size()
        .unstack(fill_value=0)
        .reset_index()
    )
    for col in ["PASS", "FAIL", "WARN"]:
        if col not in dataset_quality.columns:
            dataset_quality[col] = 0

    dataset_quality["total"] = dataset_quality[["PASS", "FAIL", "WARN"]].sum(axis=1)
    dataset_quality["pass_rate"] = (dataset_quality["PASS"] / dataset_quality["total"] * 100).round(1)

    cols = st.columns(len(dataset_quality))
    for i, (_, row) in enumerate(dataset_quality.iterrows()):
        with cols[i]:
            color = "🟢" if row["pass_rate"] >= 80 else "🟡" if row["pass_rate"] >= 60 else "🔴"
            st.metric(
                f"{color} {row['dataset'].title()}",
                f"{row['pass_rate']}% pass rate",
                f"{int(row['FAIL'])} failed / {int(row['WARN'])} warned",
                delta_color="inverse",
            )

    # Check breakdown chart
    fig3 = go.Figure()
    for status, color in [("PASS", "#2ecc71"), ("WARN", "#f39c12"), ("FAIL", "#e74c3c")]:
        fig3.add_trace(go.Bar(
            name=status,
            x=dataset_quality["dataset"],
            y=dataset_quality[status],
            marker_color=color,
        ))
    fig3.update_layout(
        barmode="stack", height=260,
        margin=dict(t=10, b=10, l=20, r=20),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", y=1.1),
        yaxis=dict(gridcolor="#2a2a2a"),
    )
    st.plotly_chart(fig3, use_container_width=True)

st.divider()

# Detail tabs
tab_runs, tab_checks, tab_failed, tab_explore = st.tabs([
    f"📋 Run History ({total_runs})",
    f"✅ All Quality Checks ({total_checks})",
    f"🔴 Failed Checks ({sum(1 for c in checks if c['status'] == 'FAIL')})",
    "🔍 Explore Data",
])

with tab_runs:
    if runs:
        df_runs = pd.DataFrame(runs)
        df_runs["status"] = df_runs["status"].map(
            lambda x: {"SUCCESS": "✅ SUCCESS", "FAILED": "❌ FAILED", "RUNNING": "🔄 RUNNING"}.get(x, x)
        )
        df_runs["duration"] = df_runs.apply(lambda r: (
            f"{(datetime.fromisoformat(r['finished_at']) - datetime.fromisoformat(r['started_at'])).seconds}s"
            if r["finished_at"] else "—"
        ), axis=1)
        display_cols = ["run_id", "dataset", "status", "stage", "rows_ingested", "rows_passed", "rows_failed", "duration", "started_at"]
        st.dataframe(df_runs[[c for c in display_cols if c in df_runs.columns]], use_container_width=True, height=380)
    else:
        st.info("No runs yet.")

with tab_checks:
    if checks:
        df_checks = pd.DataFrame(checks)
        df_checks["status"] = df_checks["status"].map(
            lambda x: {"PASS": "✅ PASS", "FAIL": "❌ FAIL", "WARN": "⚠️ WARN"}.get(x, x)
        )
        st.dataframe(df_checks[["run_id", "dataset", "check_name", "check_type", "column", "status", "severity", "expected", "actual", "rows_affected"]], use_container_width=True, height=380)
    else:
        st.info("No checks yet.")

with tab_failed:
    failed = [c for c in checks if c["status"] == "FAIL"]
    if failed:
        df_failed = pd.DataFrame(failed)
        st.dataframe(
            df_failed[["run_id", "dataset", "check_name", "check_type", "column", "severity", "expected", "actual", "rows_affected"]],
            use_container_width=True, height=380
        )
    else:
        st.success("No failed checks — all quality rules passing.")

with tab_explore:
    st.subheader("Explore Processed Data")
    explore_dataset = st.selectbox("Dataset", list(configs.keys()), format_func=lambda x: configs[x].display_name)
    explore_runs = [r for r in runs if r["dataset"] == explore_dataset and r["status"] == "SUCCESS"]

    if not explore_runs:
        st.info(f"No successful runs for {configs[explore_dataset].display_name} yet.")
    else:
        selected_run = st.selectbox(
            "Select run",
            [r["run_id"] for r in explore_runs],
            format_func=lambda rid: next(
                f"{r['run_id']} — {r['started_at'][:19]} — {r['rows_passed']:,} rows"
                for r in explore_runs if r["run_id"] == rid
            ),
        )

        table_map = {
            "prices": "processed_prices",
            "positions": "processed_positions",
            "transactions": "processed_transactions",
        }
        table = table_map.get(explore_dataset)
        if table:
            import sqlalchemy
            from sqlalchemy import create_engine, text
            engine = create_engine(f"sqlite:///{db.DB_PATH}")
            with engine.connect() as conn:
                df_explore = pd.read_sql(
                    text(f"SELECT * FROM {table} WHERE run_id = :run_id LIMIT 500"),
                    conn, params={"run_id": selected_run}
                )
            st.caption(f"{len(df_explore):,} rows from run {selected_run}")
            st.dataframe(df_explore.astype(str).replace("nan", "").replace("None", ""), use_container_width=True, height=380)
