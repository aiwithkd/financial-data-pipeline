from __future__ import annotations

import pandas as pd


def transform_prices(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in ["close_price", "bid_price", "ask_price"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").round(4)
    if "volume" in df.columns:
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0).astype(int)
    if "price_currency" in df.columns:
        df["price_currency"] = df["price_currency"].str.upper().str.strip()
    # Derived: bid-ask spread
    if "bid_price" in df.columns and "ask_price" in df.columns:
        df["spread"] = (df["ask_price"] - df["bid_price"]).round(4)
        df["spread_bps"] = ((df["spread"] / df["close_price"]) * 10000).round(2)
    return df


def transform_positions(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in ["quantity", "price", "market_value"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "asset_class" in df.columns:
        df["asset_class"] = df["asset_class"].str.strip().str.title()
    if "currency" in df.columns:
        df["currency"] = df["currency"].str.upper().str.strip()
    # Derived: recalculated market value for consistency check
    if "quantity" in df.columns and "price" in df.columns:
        df["mv_recalculated"] = (df["quantity"] * df["price"]).round(2)
        df["mv_variance_pct"] = (
            (df["market_value"] - df["mv_recalculated"]).abs() / df["mv_recalculated"].abs() * 100
        ).round(2)
    return df


def transform_transactions(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in ["quantity", "trade_price", "gross_amount", "net_amount", "commission"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "transaction_type" in df.columns:
        df["transaction_type"] = df["transaction_type"].str.upper().str.strip()
    for col in ["trade_date", "settlement_date"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce").dt.strftime("%Y-%m-%d")
    # Derived: settlement lag in days
    if "trade_date" in df.columns and "settlement_date" in df.columns:
        td = pd.to_datetime(df["trade_date"], errors="coerce")
        sd = pd.to_datetime(df["settlement_date"], errors="coerce")
        df["settlement_lag_days"] = (sd - td).dt.days
    return df


TRANSFORM_MAP = {
    "prices": transform_prices,
    "positions": transform_positions,
    "transactions": transform_transactions,
}


def transform(dataset: str, df: pd.DataFrame) -> pd.DataFrame:
    fn = TRANSFORM_MAP.get(dataset)
    if fn:
        return fn(df)
    return df
