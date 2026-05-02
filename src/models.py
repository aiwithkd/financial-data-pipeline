from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class PipelineRun:
    run_id: str
    dataset: str
    status: str          # RUNNING | SUCCESS | FAILED
    started_at: datetime
    finished_at: Optional[datetime] = None
    rows_ingested: int = 0
    rows_passed: int = 0
    rows_failed: int = 0
    error_message: str = ""
    stage: str = ""      # ingest | transform | quality | complete


@dataclass
class QualityCheck:
    check_id: str
    run_id: str
    dataset: str
    check_name: str
    check_type: str      # null_check | range_check | schema_check | referential | duplicate
    column: str
    status: str          # PASS | FAIL | WARN
    expected: str
    actual: str
    rows_affected: int = 0
    severity: str = "HIGH"   # HIGH | MEDIUM | LOW


@dataclass
class QualityRule:
    name: str
    check_type: str
    column: str
    severity: str = "HIGH"
    params: dict = field(default_factory=dict)


@dataclass
class DatasetConfig:
    name: str
    display_name: str
    raw_file: str
    rules: list[QualityRule] = field(default_factory=list)
