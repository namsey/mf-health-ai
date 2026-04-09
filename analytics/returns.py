"""
analytics/returns.py
---------------------
Return calculation engine.

Functions:
  calculate_cagr   — Compound Annual Growth Rate (point-to-point)
  calculate_xirr   — XIRR for SIP cash-flow series (Newton-Raphson)
  compute_all_returns — Batch CAGR for a NAV DataFrame
"""

import numpy as np
import pandas as pd
import logging
from typing import Optional

logger = logging.getLogger(__name__)


# ── CAGR ──────────────────────────────────────────────────────────────────────

def calculate_cagr(df: pd.DataFrame, years: int) -> Optional[float]:
    """
    CAGR over N years using actual elapsed days (not calendar approximation).
    More accurate than point-to-point % for periods != exactly N years.
    """
    if df.empty:
        return None

    df = df.sort_values("date").copy()
    latest_date = df["date"].max()
    target_date = latest_date - pd.DateOffset(years=years)

    past = df[df["date"] <= target_date]
    if past.empty:
        return None

    start_nav = past.iloc[-1]["nav"]
    end_nav   = df.iloc[-1]["nav"]

    if start_nav <= 0 or end_nav <= 0:
        return None

    # Use actual elapsed years for precision
    actual_years = (latest_date - past.iloc[-1]["date"]).days / 365.25
    if actual_years < 0.5:
        return None

    cagr = ((end_nav / start_nav) ** (1.0 / actual_years) - 1.0) * 100
    return round(cagr, 2)


# ── XIRR ──────────────────────────────────────────────────────────────────────

def calculate_xirr(cashflows: list[dict]) -> Optional[float]:
    """
    XIRR for irregular cash flows (SIP investments).

    cashflows: list of {"date": datetime/Timestamp, "amount": float}
      - Investments are NEGATIVE amounts
      - Current value (redemption) is POSITIVE amount
      - Must have at least one negative and one positive entry

    Returns annualised rate as percentage, e.g. 12.5 means 12.5 % p.a.
    """
    if len(cashflows) < 2:
        return None

    dates   = [pd.Timestamp(cf["date"]) for cf in cashflows]
    amounts = [cf["amount"]              for cf in cashflows]
    base_dt = dates[0]

    has_neg = any(a < 0 for a in amounts)
    has_pos = any(a > 0 for a in amounts)
    if not (has_neg and has_pos):
        return None

    def npv(rate: float) -> float:
        return sum(
            a / (1.0 + rate) ** ((d - base_dt).days / 365.25)
            for a, d in zip(amounts, dates)
        )

    # Bracket search + bisection fallback
    try:
        lo, hi = -0.9, 100.0
        if npv(lo) * npv(hi) > 0:
            return None
        # Bisection (simple, always converges)
        for _ in range(100):
            mid = (lo + hi) / 2.0
            if abs(hi - lo) < 1e-8:
                break
            if npv(mid) * npv(lo) <= 0:
                hi = mid
            else:
                lo = mid
        return round(mid * 100, 2)
    except Exception as exc:
        logger.debug("XIRR failed: %s", exc)
        return None


# ── Batch helper ──────────────────────────────────────────────────────────────

def compute_all_returns(nav_df: pd.DataFrame) -> pd.DataFrame:
    """Return a DataFrame with 1Y / 3Y / 5Y CAGR for each amfi_code."""
    rows = []
    for code, grp in nav_df.groupby("amfi_code"):
        rows.append({
            "amfi_code": code,
            "return_1y": calculate_cagr(grp, 1),
            "return_3y": calculate_cagr(grp, 3),
            "return_5y": calculate_cagr(grp, 5),
        })
    return pd.DataFrame(rows)
