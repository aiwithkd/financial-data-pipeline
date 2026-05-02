from __future__ import annotations

import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional

DB_PATH = Path(__file__).parent.parent / "pipeline.db"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS pipeline_runs (
            run_id        TEXT PRIMARY KEY,
            dataset       TEXT NOT NULL,
            status        TEXT NOT NULL,
            stage         TEXT NOT NULL DEFAULT '',
            started_at    TEXT NOT NULL,
            finished_at   TEXT,
            rows_ingested INTEGER DEFAULT 0,
            rows_passed   INTEGER DEFAULT 0,
            rows_failed   INTEGER DEFAULT 0,
            error_message TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS quality_checks (
            check_id      TEXT PRIMARY KEY,
            run_id        TEXT NOT NULL,
            dataset       TEXT NOT NULL,
            check_name    TEXT NOT NULL,
            check_type    TEXT NOT NULL,
            column        TEXT NOT NULL,
            status        TEXT NOT NULL,
            expected      TEXT NOT NULL,
            actual        TEXT NOT NULL,
            rows_affected INTEGER DEFAULT 0,
            severity      TEXT DEFAULT 'HIGH',
            FOREIGN KEY (run_id) REFERENCES pipeline_runs(run_id)
        );

        """)


def insert_run(run) -> None:
    with get_conn() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO pipeline_runs
            (run_id, dataset, status, stage, started_at, finished_at, rows_ingested, rows_passed, rows_failed, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            run.run_id, run.dataset, run.status, run.stage,
            run.started_at.isoformat(),
            run.finished_at.isoformat() if run.finished_at else None,
            run.rows_ingested, run.rows_passed, run.rows_failed,
            run.error_message,
        ))


def update_run(run) -> None:
    insert_run(run)


def insert_checks(checks: list) -> None:
    if not checks:
        return
    with get_conn() as conn:
        conn.executemany("""
            INSERT OR REPLACE INTO quality_checks
            (check_id, run_id, dataset, check_name, check_type, column, status, expected, actual, rows_affected, severity)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            (c.check_id, c.run_id, c.dataset, c.check_name, c.check_type,
             c.column, c.status, c.expected, c.actual, c.rows_affected, c.severity)
            for c in checks
        ])


def fetch_runs(limit: int = 100) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM pipeline_runs ORDER BY started_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def fetch_checks(run_id: Optional[str] = None, limit: int = 500) -> list[dict]:
    with get_conn() as conn:
        if run_id:
            rows = conn.execute(
                "SELECT * FROM quality_checks WHERE run_id = ? ORDER BY status DESC, severity DESC",
                (run_id,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM quality_checks ORDER BY run_id DESC, status DESC LIMIT ?", (limit,)
            ).fetchall()
    return [dict(r) for r in rows]


def fetch_dataset_stats() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT
                dataset,
                COUNT(*) as total_runs,
                SUM(CASE WHEN status = 'SUCCESS' THEN 1 ELSE 0 END) as success_runs,
                SUM(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END) as failed_runs,
                MAX(started_at) as last_run,
                AVG(rows_ingested) as avg_rows,
                SUM(rows_ingested) as total_rows
            FROM pipeline_runs
            GROUP BY dataset
        """).fetchall()
    return [dict(r) for r in rows]


def fetch_quality_trend(dataset: str, limit: int = 20) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT
                r.run_id,
                r.started_at,
                r.dataset,
                COUNT(q.check_id) as total_checks,
                SUM(CASE WHEN q.status = 'PASS' THEN 1 ELSE 0 END) as passed,
                SUM(CASE WHEN q.status = 'FAIL' THEN 1 ELSE 0 END) as failed,
                SUM(CASE WHEN q.status = 'WARN' THEN 1 ELSE 0 END) as warned
            FROM pipeline_runs r
            LEFT JOIN quality_checks q ON r.run_id = q.run_id
            WHERE r.dataset = ?
            GROUP BY r.run_id
            ORDER BY r.started_at DESC
            LIMIT ?
        """, (dataset, limit)).fetchall()
    return [dict(r) for r in rows]


def clear_processed(run_id: str, dataset: str) -> None:
    table_map = {
        "prices": "processed_prices",
        "positions": "processed_positions",
        "transactions": "processed_transactions",
    }
    table = table_map.get(dataset)
    if table:
        with get_conn() as conn:
            conn.execute(f"DELETE FROM {table} WHERE run_id = ?", (run_id,))


def insert_processed(dataset: str, run_id: str, df) -> None:
    import pandas as pd
    table_map = {
        "prices": "processed_prices",
        "positions": "processed_positions",
        "transactions": "processed_transactions",
    }
    table = table_map.get(dataset)
    if not table:
        return
    df = df.copy()
    df["run_id"] = run_id
    df["loaded_at"] = datetime.utcnow().isoformat()
    import sqlalchemy
    from sqlalchemy import create_engine
    engine = create_engine(f"sqlite:///{DB_PATH}")
    df.to_sql(table, engine, if_exists="append", index=False)
