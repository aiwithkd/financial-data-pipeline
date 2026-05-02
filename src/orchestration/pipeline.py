from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path

from src import database as db
from src.ingestion.loader import load_raw
from src.models import DatasetConfig, PipelineRun
from src.quality.engine import run_checks
from src.transformation.transforms import transform

ROOT = Path(__file__).parent.parent.parent


def run_pipeline(dataset_name: str, config: DatasetConfig) -> PipelineRun:
    run_id = str(uuid.uuid4())[:8]
    run = PipelineRun(
        run_id=run_id,
        dataset=dataset_name,
        status="RUNNING",
        started_at=datetime.utcnow(),
        stage="ingest",
    )
    db.insert_run(run)

    try:
        # Stage 1: Ingest
        raw_path = ROOT / config.raw_file
        if not raw_path.exists():
            raise FileNotFoundError(f"Raw file not found: {raw_path}")

        df = load_raw(raw_path)
        run.rows_ingested = len(df)
        run.stage = "quality"
        db.update_run(run)

        # Stage 2: Quality checks
        clean_df, checks = run_checks(df, config.rules, run_id, dataset_name)
        db.insert_checks(checks)

        failed_checks = [c for c in checks if c.status == "FAIL"]
        run.rows_passed = len(clean_df)
        run.rows_failed = run.rows_ingested - len(clean_df)
        run.stage = "transform"
        db.update_run(run)

        # Stage 3: Transform
        transformed_df = transform(dataset_name, clean_df)
        run.stage = "load"
        db.update_run(run)

        # Stage 4: Load to DB
        db.insert_processed(dataset_name, run_id, transformed_df)

        run.status = "SUCCESS"
        run.stage = "complete"
        run.finished_at = datetime.utcnow()
        db.update_run(run)

    except Exception as e:
        run.status = "FAILED"
        run.error_message = str(e)
        run.finished_at = datetime.utcnow()
        db.update_run(run)

    return run


def run_all_pipelines(configs: dict[str, DatasetConfig]) -> list[PipelineRun]:
    return [run_pipeline(name, cfg) for name, cfg in configs.items()]
