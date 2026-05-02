from __future__ import annotations

from pathlib import Path

import pandas as pd


def load_raw(path: Path) -> pd.DataFrame:
    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            df = pd.read_csv(path, encoding=enc)
            df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
            df = df.loc[:, ~df.columns.str.startswith("unnamed")]
            return df
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Could not decode {path}")
