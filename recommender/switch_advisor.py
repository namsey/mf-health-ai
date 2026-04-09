"""
recommender/switch_advisor.py
------------------------------
Category-aware switch recommendation engine.

Rules:
  1. Only suggest switching within the same fund category
     (never swap Large Cap → Small Cap — different risk profiles)
  2. Pull switch target from the fund universe, not the user's portfolio
  3. Switch is recommended only when the score gap is meaningful (>= 10 pts)
  4. Apply risk-profile filter: aggressive users can be shown higher-volatility
     alternatives; conservative users prefer low-volatility alternatives
"""

import logging
from typing import Optional
import pandas as pd

logger = logging.getLogger(__name__)

SCORE_GAP_THRESHOLD = 10   # Minimum score improvement to recommend a switch


def get_switch_recommendations(portfolio_df: pd.DataFrame,
                               universe_df: pd.DataFrame,
                               risk_profile: str = "moderate") -> list[dict]:
    """
    portfolio_df : scored DataFrame of user's current holdings
    universe_df  : scored DataFrame of all market funds (same schema)
    risk_profile : 'conservative' | 'moderate' | 'aggressive'

    Returns list of recommendation dicts.
    """
    if universe_df is None or universe_df.empty:
        logger.warning("Fund universe empty — cannot generate switch recommendations")
        return []

    recommendations = []

    for _, fund in portfolio_df.iterrows():
        if fund["Status"] == "HEALTHY":
            continue   # Healthy fund — no action needed

        category = fund.get("Category", "")
        current_score = fund["Score"]

        # Filter universe to same category, excluding the fund itself
        same_cat = universe_df[
            (universe_df["Category"] == category) &
            (universe_df["AMFI Code"] != fund["AMFI Code"])
        ].copy()

        if same_cat.empty:
            logger.info("No alternatives in category '%s' for %s", category, fund["Fund Name"])
            continue

        # Apply risk-profile filter on volatility
        if risk_profile == "conservative" and "Volatility" in same_cat.columns:
            same_cat = same_cat[same_cat["Volatility"].fillna(999) < 14]
        elif risk_profile == "aggressive" and "Volatility" in same_cat.columns:
            pass   # Aggressive: all options are fine

        if same_cat.empty:
            continue

        best = same_cat.sort_values("Score", ascending=False).iloc[0]
        score_gap = best["Score"] - current_score

        if score_gap < SCORE_GAP_THRESHOLD:
            continue   # Gap too small — not worth switching

        reasons = _build_reason(fund, best)

        recommendations.append({
            "from_fund":    fund["Fund Name"],
            "from_code":    fund["AMFI Code"],
            "from_score":   current_score,
            "from_status":  fund["Status"],
            "to_fund":      best["Fund Name"],
            "to_code":      best["AMFI Code"],
            "to_score":     best["Score"],
            "category":     category,
            "score_gain":   round(score_gap, 1),
            "reasons":      reasons,
        })

    logger.info("Generated %d switch recommendations", len(recommendations))
    return recommendations


def _build_reason(current: pd.Series, best: pd.Series) -> list[str]:
    """Generate human-readable reasons for the switch."""
    reasons = []

    def diff(metric, label, higher_is_better=True):
        a = current.get(metric)
        b = best.get(metric)
        if a is None or b is None or pd.isna(a) or pd.isna(b):
            return
        gap = b - a
        if higher_is_better and gap > 0.5:
            reasons.append(f"Better {label}: {b:.1f} vs {a:.1f}")
        elif not higher_is_better and gap < -0.5:
            reasons.append(f"Lower {label}: {b:.1f}% vs {a:.1f}%")

    diff("3Y Return",    "3Y CAGR (%)")
    diff("5Y Return",    "5Y CAGR (%)")
    diff("Sharpe",       "Sharpe Ratio")
    diff("Max Drawdown", "drawdown (%)", higher_is_better=False)

    if not reasons:
        reasons.append(f"Significantly higher composite score ({best['Score']} vs {current['Score']})")

    return reasons
