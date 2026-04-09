"""
analytics/risk.py
------------------
Industry-standard risk metrics:
  - Volatility          (annualised std dev of daily returns)
  - Max Drawdown        (worst peak-to-trough decline)
  - Sharpe Ratio        (risk-adjusted return)
  - Sortino Ratio       (penalises only downside volatility)
  - Beta                (sensitivity to market / benchmark)
  - Alpha               (Jensen's alpha vs benchmark)
  - Consistency         (% of positive return days)
"""

import numpy as np
import pandas as pd
import logging
from typing import Optional

from config.settings import settings

logger = logging.getLogger(__name__)

RISK_FREE_DAILY = (1 + settings.risk_free_rate) ** (1 / 252) - 1


# ── Internal helpers ──────────────────────────────────────────────────────────

def _daily_returns(df: pd.DataFrame) -> pd.Series:
    """Clean daily return series from a NAV DataFrame."""
    nav = df.sort_values("date")["nav"]
    ret = nav.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    return ret[ret != 0]   # Drop days with zero change (non-trading)


def _align(series_a: pd.Series, series_b: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Align two return series on their common dates."""
    combined = pd.DataFrame({"a": series_a, "b": series_b}).dropna()
    return combined["a"], combined["b"]


# ── Public metrics ────────────────────────────────────────────────────────────

def calculate_volatility(df: pd.DataFrame) -> Optional[float]:
    """Annualised volatility (%) = daily_std * sqrt(252) * 100."""
    ret = _daily_returns(df)
    if ret.empty:
        return None
    return round(ret.std() * np.sqrt(settings.trading_days) * 100, 2)


def calculate_max_drawdown(df: pd.DataFrame) -> Optional[float]:
    """Maximum peak-to-trough drawdown (%) — negative value."""
    nav = df.sort_values("date")["nav"]
    if nav.empty:
        return None
    peak = nav.cummax()
    dd   = (nav - peak) / peak * 100
    return round(dd.min(), 2)


def calculate_consistency(df: pd.DataFrame) -> Optional[float]:
    """Percentage of trading days with positive return."""
    ret = _daily_returns(df)
    if ret.empty:
        return None
    return round((ret > 0).sum() / len(ret) * 100, 2)


def calculate_sharpe(df: pd.DataFrame) -> Optional[float]:
    """
    Sharpe Ratio = (Annualised Return - Risk Free Rate) / Annualised Volatility.
    Uses geometric mean of daily returns for annualised return.
    """
    ret = _daily_returns(df)
    if ret.empty or len(ret) < 30:
        return None
    excess = ret - RISK_FREE_DAILY
    if excess.std() == 0:
        return None
    sharpe = (excess.mean() / excess.std()) * np.sqrt(settings.trading_days)
    return round(sharpe, 3)


def calculate_sortino(df: pd.DataFrame) -> Optional[float]:
    """
    Sortino Ratio = (Annualised Return - Risk Free Rate) / Downside Deviation.
    Only penalises negative excess returns (unlike Sharpe which penalises all vol).
    """
    ret = _daily_returns(df)
    if ret.empty or len(ret) < 30:
        return None
    excess     = ret - RISK_FREE_DAILY
    downside   = excess[excess < 0]
    if downside.empty or downside.std() == 0:
        return None
    down_dev   = downside.std() * np.sqrt(settings.trading_days)
    ann_excess = excess.mean()  * settings.trading_days
    return round(ann_excess / down_dev, 3)


def calculate_beta(fund_df: pd.DataFrame, benchmark_df: pd.DataFrame) -> Optional[float]:
    """
    Beta = Cov(fund, benchmark) / Var(benchmark).
    Fund and benchmark must be aligned on dates.
    """
    if fund_df.empty or benchmark_df.empty:
        return None

    fund_ret = _daily_returns(fund_df)
    bench_ret = _daily_returns(benchmark_df)
    fund_ret.index  = fund_df.sort_values("date")["date"].values[-len(fund_ret):]
    bench_ret.index = benchmark_df.sort_values("date")["date"].values[-len(bench_ret):]

    f, b = _align(fund_ret, bench_ret)
    if len(f) < 30:
        return None

    cov_matrix = np.cov(f.values, b.values)
    bench_var  = cov_matrix[1, 1]
    if bench_var == 0:
        return None
    return round(cov_matrix[0, 1] / bench_var, 3)


def calculate_alpha(fund_df: pd.DataFrame, benchmark_df: pd.DataFrame,
                    beta: Optional[float] = None) -> Optional[float]:
    """
    Jensen's Alpha (annualised, %) =
      Fund_return - [RiskFree + Beta * (Market_return - RiskFree)]
    """
    if fund_df.empty or benchmark_df.empty:
        return None

    if beta is None:
        beta = calculate_beta(fund_df, benchmark_df)
    if beta is None:
        return None

    def ann_return(df):
        nav = df.sort_values("date")["nav"]
        if len(nav) < 2:
            return None
        years = (df["date"].max() - df["date"].min()).days / 365.25
        if years < 0.5:
            return None
        return ((nav.iloc[-1] / nav.iloc[0]) ** (1 / years) - 1) * 100

    fund_ret  = ann_return(fund_df)
    bench_ret = ann_return(benchmark_df)
    if fund_ret is None or bench_ret is None:
        return None

    rf_pct = settings.risk_free_rate * 100
    alpha  = fund_ret - (rf_pct + beta * (bench_ret - rf_pct))
    return round(alpha, 2)


# ── Bundle ────────────────────────────────────────────────────────────────────

def compute_all_risk_metrics(fund_df: pd.DataFrame,
                             benchmark_df: pd.DataFrame) -> dict:
    """Compute all risk metrics in one pass for a single fund."""
    beta = calculate_beta(fund_df, benchmark_df)
    return {
        "volatility":   calculate_volatility(fund_df),
        "max_drawdown": calculate_max_drawdown(fund_df),
        "consistency":  calculate_consistency(fund_df),
        "sharpe":       calculate_sharpe(fund_df),
        "sortino":      calculate_sortino(fund_df),
        "beta":         beta,
        "alpha":        calculate_alpha(fund_df, benchmark_df, beta),
    }
