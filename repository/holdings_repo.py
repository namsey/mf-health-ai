"""
repository/holdings_repo.py
----------------------------
Stores and retrieves the investor's actual purchase details.

This is separate from portfolio.json (which just has fund metadata).
Holdings capture: units purchased, purchase NAV, purchase date, SIP history.
These are needed to calculate real P&L, XIRR, and cost basis.

Storage: data/holdings.json
Schema per holding:
  {
    "amfi_code":       "122639",
    "transactions": [
      {
        "date":        "2021-06-01",
        "type":        "BUY" | "SIP" | "REDEEM",
        "units":       150.234,
        "nav":         42.55,
        "amount":      6391.45
      }
    ]
  }
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

from config.settings import settings

logger = logging.getLogger(__name__)

HOLDINGS_PATH = settings.data_dir / "holdings.json"


# ── Internal helpers ──────────────────────────────────────────────────────────

def _load() -> dict:
    if not HOLDINGS_PATH.exists():
        return {}
    try:
        with open(HOLDINGS_PATH) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def _save(data: dict) -> None:
    with open(HOLDINGS_PATH, "w") as f:
        json.dump(data, f, indent=2, default=str)


# ── Public API ────────────────────────────────────────────────────────────────

def get_holding(amfi_code: str) -> Optional[dict]:
    """Return holding dict for one fund, or None if not recorded."""
    return _load().get(str(amfi_code))


def get_all_holdings() -> dict:
    """Return all holdings keyed by amfi_code."""
    return _load()


def add_transaction(amfi_code: str, date: str, txn_type: str,
                    units: float, nav: float) -> None:
    """
    Add a purchase, SIP, or redemption transaction.
    amount is derived from units × nav.
    """
    data = _load()
    code = str(amfi_code)

    if code not in data:
        data[code] = {"amfi_code": code, "transactions": []}

    txn = {
        "date":   date,
        "type":   txn_type.upper(),
        "units":  round(float(units), 4),
        "nav":    round(float(nav), 4),
        "amount": round(float(units) * float(nav), 2),
    }
    data[code]["transactions"].append(txn)
    data[code]["transactions"].sort(key=lambda x: x["date"])
    _save(data)
    logger.info("Added %s transaction for %s: %s units @ ₹%s", txn_type, code, units, nav)


def remove_holding(amfi_code: str) -> bool:
    data = _load()
    if str(amfi_code) not in data:
        return False
    del data[str(amfi_code)]
    _save(data)
    return True


def remove_transaction(amfi_code: str, index: int) -> bool:
    data = _load()
    code = str(amfi_code)
    if code not in data or index >= len(data[code]["transactions"]):
        return False
    data[code]["transactions"].pop(index)
    _save(data)
    return True


def compute_holding_summary(amfi_code: str, current_nav: float) -> Optional[dict]:
    """
    Derive: total_units, total_invested, current_value, P&L, avg_cost_nav.
    Returns None if no transactions recorded.
    """
    holding = get_holding(str(amfi_code))
    if not holding or not holding["transactions"]:
        return None

    txns = holding["transactions"]
    total_units    = 0.0
    total_invested = 0.0

    for t in txns:
        if t["type"] in ("BUY", "SIP"):
            total_units    += t["units"]
            total_invested += t["amount"]
        elif t["type"] == "REDEEM":
            total_units    -= t["units"]
            # Reduce invested proportionally (FIFO approximation)
            if total_units + t["units"] > 0:
                total_invested -= (t["units"] / (total_units + t["units"])) * total_invested

    total_units    = max(total_units, 0)
    total_invested = max(total_invested, 0)
    current_value  = round(total_units * current_nav, 2)
    pnl            = round(current_value - total_invested, 2)
    pnl_pct        = round((pnl / total_invested * 100) if total_invested > 0 else 0, 2)
    avg_cost_nav   = round(total_invested / total_units, 4) if total_units > 0 else 0

    return {
        "total_units":    round(total_units, 4),
        "total_invested": round(total_invested, 2),
        "current_value":  current_value,
        "current_nav":    current_nav,
        "avg_cost_nav":   avg_cost_nav,
        "pnl":            pnl,
        "pnl_pct":        pnl_pct,
        "num_transactions": len(txns),
        "transactions":   txns,
    }
