"""Generate realistic raw financial data with intentional quality issues for demo."""
from __future__ import annotations

import os
import random
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
rng = np.random.default_rng(SEED)
random.seed(SEED)

OUT = Path(os.path.abspath(__file__)).parent.parent / "data" / "raw"
OUT.mkdir(parents=True, exist_ok=True)

ISINS = [f"US{str(i).zfill(10)}" for i in range(1000, 1150)]
ACCOUNTS = [f"ACC-{i}" for i in range(10001, 10041)]
CURRENCIES = ["USD", "GBP", "EUR"]
BROKERS = [f"BROKER_{i:03d}" for i in range(1, 6)]


def gen_prices():
    n = 200
    rows = []
    for i, isin in enumerate(ISINS[:n]):
        cp = round(rng.uniform(10, 500), 4)
        rows.append({
            "isin": isin,
            "close_price": cp,
            "bid_price": round(cp - rng.uniform(0.01, 0.10), 4),
            "ask_price": round(cp + rng.uniform(0.01, 0.10), 4),
            "volume": int(rng.integers(100_000, 5_000_000)),
            "price_date": "2024-01-15",
            "price_currency": "USD",
        })

    df = pd.DataFrame(rows)

    # Inject quality issues
    # 1. Nulls in close_price (5 rows)
    df.loc[rng.choice(df.index, 5, replace=False), "close_price"] = None

    # 2. Negative prices (3 rows — data entry error)
    df.loc[rng.choice(df.index, 3, replace=False), "close_price"] = round(-rng.uniform(1, 10), 4)

    # 3. Bid > Ask (price inversion — 4 rows)
    bad_idx = rng.choice(df.index, 4, replace=False)
    df.loc[bad_idx, "bid_price"] = df.loc[bad_idx, "ask_price"] + rng.uniform(0.5, 2.0, 4)

    # 4. Missing volume (3 rows)
    df.loc[rng.choice(df.index, 3, replace=False), "volume"] = None

    # 5. Wrong currency (2 rows — should be USD)
    df.loc[rng.choice(df.index, 2, replace=False), "price_currency"] = "XXX"

    # 6. Duplicate ISINs (2 rows)
    dup = df.iloc[:2].copy()
    df = pd.concat([df, dup], ignore_index=True)

    df.to_csv(OUT / "prices.csv", index=False)
    print(f"Prices: {len(df)} rows written with intentional quality issues")


def gen_positions():
    n = 250
    rows = []
    for _ in range(n):
        acct = random.choice(ACCOUNTS)
        isin = random.choice(ISINS)
        qty = round(random.uniform(100, 5000), 0)
        price = round(random.uniform(10, 500), 4)
        mv = round(qty * price, 2)
        rows.append({
            "account_id": acct,
            "security_id": isin,
            "asset_class": random.choice(["Equity", "Bond", "ETF"]),
            "quantity": qty,
            "price": price,
            "market_value": mv,
            "currency": random.choice(CURRENCIES),
            "price_date": "2024-01-15",
        })

    df = pd.DataFrame(rows).drop_duplicates(subset=["account_id", "security_id"])

    # Inject quality issues
    # 1. Null account_id (3 rows)
    df.loc[rng.choice(df.index, 3, replace=False), "account_id"] = None

    # 2. Negative market_value (2 rows)
    df.loc[rng.choice(df.index, 2, replace=False), "market_value"] = round(-rng.uniform(100, 5000), 2)

    # 3. Quantity = 0 (should not exist — zero positions) (4 rows)
    df.loc[rng.choice(df.index, 4, replace=False), "quantity"] = 0

    # 4. market_value inconsistent with qty * price (5 rows — stale MV)
    stale_idx = rng.choice(df.index, 5, replace=False)
    df.loc[stale_idx, "market_value"] = df.loc[stale_idx, "market_value"] * rng.uniform(1.05, 1.20, 5)

    # 5. Invalid currency (3 rows)
    df.loc[rng.choice(df.index, 3, replace=False), "currency"] = "ZZZ"

    df.to_csv(OUT / "positions.csv", index=False)
    print(f"Positions: {len(df)} rows written with intentional quality issues")


def gen_transactions():
    n = 150
    rows = []
    for _ in range(n):
        acct = random.choice(ACCOUNTS)
        isin = random.choice(ISINS[:50])
        qty = round(random.uniform(100, 1000), 0)
        price = round(random.uniform(10, 300), 4)
        gross = round(qty * price, 2)
        comm = round(gross * 0.001, 2)
        rows.append({
            "account_id": acct,
            "isin": isin,
            "transaction_type": random.choice(["BUY", "SELL"]),
            "trade_date": "2024-01-15",
            "settlement_date": "2024-01-17",
            "quantity": qty,
            "trade_price": price,
            "gross_amount": gross,
            "commission": comm,
            "net_amount": round(gross + comm, 2),
            "currency": "USD",
        })

    df = pd.DataFrame(rows)

    # Inject quality issues
    # 1. Null account_id (3 rows)
    df.loc[rng.choice(df.index, 3, replace=False), "account_id"] = None

    # 2. Invalid transaction_type (3 rows — bad upstream system)
    df.loc[rng.choice(df.index, 3, replace=False), "transaction_type"] = "UNKNOWN"

    # 3. net_amount < gross_amount (commission sign error — 4 rows)
    bad_idx = rng.choice(df.index, 4, replace=False)
    df.loc[bad_idx, "net_amount"] = df.loc[bad_idx, "gross_amount"] - df.loc[bad_idx, "commission"]

    # 4. Settlement before trade date (3 rows — date logic error)
    df.loc[rng.choice(df.index, 3, replace=False), "settlement_date"] = "2024-01-13"

    # 5. Zero quantity (2 rows)
    df.loc[rng.choice(df.index, 2, replace=False), "quantity"] = 0

    df.to_csv(OUT / "transactions.csv", index=False)
    print(f"Transactions: {len(df)} rows written with intentional quality issues")


if __name__ == "__main__":
    gen_prices()
    gen_positions()
    gen_transactions()
    print(f"\nSample data written to {OUT}")
