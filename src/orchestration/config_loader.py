from __future__ import annotations

from pathlib import Path

import yaml

from src.models import DatasetConfig, QualityRule

_CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "pipeline.yaml"


def load_config() -> dict[str, DatasetConfig]:
    with open(_CONFIG_PATH) as f:
        raw = yaml.safe_load(f)

    configs: dict[str, DatasetConfig] = {}
    for name, cfg in raw.get("datasets", {}).items():
        rules = [
            QualityRule(
                name=r["name"],
                check_type=r["check_type"],
                column=r["column"],
                severity=r.get("severity", "HIGH"),
                params=r.get("params", {}),
            )
            for r in cfg.get("rules", [])
        ]
        configs[name] = DatasetConfig(
            name=name,
            display_name=cfg.get("display_name", name),
            raw_file=cfg.get("raw_file", f"data/raw/{name}.csv"),
            rules=rules,
        )
    return configs
