from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from src.orchestration.config_loader import load_config
from src.orchestration.pipeline import run_all_pipelines

_scheduler: BackgroundScheduler | None = None


def _job():
    configs = load_config()
    run_all_pipelines(configs)


def start(interval_minutes: int = 5) -> BackgroundScheduler:
    global _scheduler
    if _scheduler and _scheduler.running:
        return _scheduler
    _scheduler = BackgroundScheduler()
    _scheduler.add_job(
        _job,
        trigger=IntervalTrigger(minutes=interval_minutes),
        id="pipeline_job",
        name="Financial Data Pipeline",
        replace_existing=True,
    )
    _scheduler.start()
    return _scheduler


def stop() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)


def is_running() -> bool:
    return _scheduler is not None and _scheduler.running


def next_run_time() -> str:
    if _scheduler and _scheduler.running:
        job = _scheduler.get_job("pipeline_job")
        if job and job.next_run_time:
            return job.next_run_time.strftime("%Y-%m-%d %H:%M:%S UTC")
    return "—"
