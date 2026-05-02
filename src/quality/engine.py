from __future__ import annotations

import uuid
from datetime import datetime

import pandas as pd

from src.models import QualityCheck, QualityRule


def run_checks(df: pd.DataFrame, rules: list[QualityRule], run_id: str, dataset: str) -> tuple[pd.DataFrame, list[QualityCheck]]:
    checks: list[QualityCheck] = []
    mask_fail = pd.Series([False] * len(df), index=df.index)

    for rule in rules:
        check = _evaluate(df, rule, run_id, dataset)
        checks.append(check)
        if check.status == "FAIL" and rule.severity == "HIGH":
            col = rule.column
            if rule.check_type == "null_check" and col in df.columns:
                mask_fail |= df[col].isna()
            elif rule.check_type == "range_check" and col in df.columns:
                mn = rule.params.get("min")
                mx = rule.params.get("max")
                series = pd.to_numeric(df[col], errors="coerce")
                if mn is not None:
                    mask_fail |= series < mn
                if mx is not None:
                    mask_fail |= series > mx
            elif rule.check_type == "allowed_values" and col in df.columns:
                allowed = rule.params.get("values", [])
                mask_fail |= ~df[col].isin(allowed) & df[col].notna()

    clean_df = df[~mask_fail].reset_index(drop=True)
    return clean_df, checks


def _evaluate(df: pd.DataFrame, rule: QualityRule, run_id: str, dataset: str) -> QualityCheck:
    col = rule.column
    ctype = rule.check_type

    if ctype == "null_check":
        null_count = int(df[col].isna().sum()) if col in df.columns else 0
        threshold = rule.params.get("max_null_pct", 0)
        actual_pct = round(null_count / len(df) * 100, 2) if len(df) > 0 else 0
        status = "PASS" if actual_pct <= threshold else ("WARN" if rule.severity == "LOW" else "FAIL")
        return _make_check(run_id, dataset, rule,
                           expected=f"null% <= {threshold}%",
                           actual=f"null% = {actual_pct}% ({null_count} rows)",
                           rows_affected=null_count, status=status)

    elif ctype == "range_check":
        if col not in df.columns:
            return _make_check(run_id, dataset, rule, "col exists", "col missing", 0, "FAIL")
        series = pd.to_numeric(df[col], errors="coerce").dropna()
        mn = rule.params.get("min")
        mx = rule.params.get("max")
        violations = 0
        parts = []
        if mn is not None:
            below = int((series < mn).sum())
            violations += below
            parts.append(f"min={mn}")
        if mx is not None:
            above = int((series > mx).sum())
            violations += above
            parts.append(f"max={mx}")
        status = "PASS" if violations == 0 else ("WARN" if rule.severity == "LOW" else "FAIL")
        return _make_check(run_id, dataset, rule,
                           expected=f"range [{', '.join(parts)}]",
                           actual=f"{violations} out-of-range rows",
                           rows_affected=violations, status=status)

    elif ctype == "duplicate_check":
        cols = rule.params.get("columns", [col])
        existing = [c for c in cols if c in df.columns]
        if not existing:
            return _make_check(run_id, dataset, rule, "cols exist", "cols missing", 0, "FAIL")
        dup_count = int(df.duplicated(subset=existing).sum())
        status = "PASS" if dup_count == 0 else ("WARN" if rule.severity == "LOW" else "FAIL")
        return _make_check(run_id, dataset, rule,
                           expected="0 duplicates",
                           actual=f"{dup_count} duplicate rows",
                           rows_affected=dup_count, status=status)

    elif ctype == "allowed_values":
        if col not in df.columns:
            return _make_check(run_id, dataset, rule, "col exists", "col missing", 0, "FAIL")
        allowed = rule.params.get("values", [])
        invalid = int((~df[col].isin(allowed) & df[col].notna()).sum())
        status = "PASS" if invalid == 0 else ("WARN" if rule.severity == "LOW" else "FAIL")
        return _make_check(run_id, dataset, rule,
                           expected=f"values in {allowed}",
                           actual=f"{invalid} invalid values",
                           rows_affected=invalid, status=status)

    elif ctype == "cross_field_check":
        # Generic cross-field: e.g. bid_price < ask_price
        expr = rule.params.get("expression", "")
        if not expr:
            return _make_check(run_id, dataset, rule, "expr set", "no expression", 0, "FAIL")
        try:
            violations = int((~df.eval(expr)).sum())
        except Exception as e:
            return _make_check(run_id, dataset, rule, "expr valid", str(e), 0, "FAIL")
        status = "PASS" if violations == 0 else ("WARN" if rule.severity == "LOW" else "FAIL")
        return _make_check(run_id, dataset, rule,
                           expected=f"{expr} for all rows",
                           actual=f"{violations} violations",
                           rows_affected=violations, status=status)

    elif ctype == "schema_check":
        required = rule.params.get("required_columns", [])
        missing = [c for c in required if c not in df.columns]
        status = "PASS" if not missing else "FAIL"
        return _make_check(run_id, dataset, rule,
                           expected=f"columns: {required}",
                           actual=f"missing: {missing}" if missing else "all present",
                           rows_affected=0, status=status)

    elif ctype == "row_count_check":
        mn = rule.params.get("min_rows", 0)
        status = "PASS" if len(df) >= mn else "FAIL"
        return _make_check(run_id, dataset, rule,
                           expected=f">= {mn} rows",
                           actual=f"{len(df)} rows",
                           rows_affected=0 if len(df) >= mn else mn - len(df),
                           status=status)

    return _make_check(run_id, dataset, rule, "known check_type", f"unknown: {ctype}", 0, "FAIL")


def _make_check(run_id, dataset, rule, expected, actual, rows_affected, status) -> QualityCheck:
    return QualityCheck(
        check_id=str(uuid.uuid4()),
        run_id=run_id,
        dataset=dataset,
        check_name=rule.name,
        check_type=rule.check_type,
        column=rule.column,
        status=status,
        expected=str(expected),
        actual=str(actual),
        rows_affected=rows_affected,
        severity=rule.severity,
    )
