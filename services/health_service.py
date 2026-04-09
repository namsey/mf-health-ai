"""
services/health_service.py
---------------------------
Orchestration layer: ties together repository, analytics, scoring, and AI.

Single entry point for the UI — never import analytics modules directly in app.py.
This enforces a clean layered architecture:

  UI (app.py)
    └── services/health_service.py
          ├── repository/  (data access)
          ├── analytics/   (computation)
          ├── scoring/     (classification)
          ├── recommender/ (advice)
          └── ai/          (explanation)
"""

import logging
import pandas as pd
from typing import Optional

from repository.portfolio_repo import get_funds, get_risk_profile
from repository.nav_repo       import load_nav
from analytics.returns         import compute_all_returns
from analytics.risk            import compute_all_risk_metrics
from scoring.health_score      import compute_total_score, get_fund_status, get_score_breakdown
from recommender.switch_advisor import get_switch_recommendations
from ai.explain                import generate_explanation

logger = logging.getLogger(__name__)


def run_portfolio_health(universe_df: Optional[pd.DataFrame] = None) -> dict:
    """
    Full health check pipeline for the user's portfolio.

    Returns:
      {
        "results":          list of fund result dicts,
        "df":               scored DataFrame,
        "recommendations":  list of switch dicts,
        "risk_profile":     str,
        "portfolio_stats":  dict,
        "nav_df":           raw NAV DataFrame,
      }
    """
    # ── 1. Load data ──────────────────────────────────────────────────────────
    funds        = get_funds()
    risk_profile = get_risk_profile()
    amfi_codes   = [f["amfi_code"] for f in funds]

    nav_df = load_nav(amfi_codes)
    if nav_df.empty:
        return {"error": "No NAV data found. Please refresh data first."}

    # Benchmark NAV for Beta / Alpha
    from config.settings import settings
    benchmark_df = load_nav([settings.nifty50_code])
    has_benchmark = not benchmark_df.empty

    # ── 2. Compute returns ────────────────────────────────────────────────────
    returns_df = compute_all_returns(nav_df)

    # ── 3. Code → name mapping ────────────────────────────────────────────────
    code_to_meta = {f["amfi_code"]: f for f in funds}

    # ── 4. Score each fund ────────────────────────────────────────────────────
    results = []

    for _, row in returns_df.iterrows():
        code  = row["amfi_code"]
        meta  = code_to_meta.get(code, {})
        group = nav_df[nav_df["amfi_code"] == code]
        bench = benchmark_df if has_benchmark else pd.DataFrame()

        risk = compute_all_risk_metrics(group, bench)

        score = compute_total_score(
            r1          = row["return_1y"],
            r3          = row["return_3y"],
            r5          = row["return_5y"],
            sharpe      = risk["sharpe"],
            sortino     = risk["sortino"],
            drawdown    = risk["max_drawdown"],
            consistency = risk["consistency"],
        )
        status = get_fund_status(score)

        breakdown = get_score_breakdown(
            row["return_1y"], row["return_3y"], row["return_5y"],
            risk["sharpe"], risk["sortino"], risk["max_drawdown"], risk["consistency"]
        )

        metrics = {
            "return_1y":   row["return_1y"],
            "return_3y":   row["return_3y"],
            "return_5y":   row["return_5y"],
            **risk,
            "score":       score,
            "status":      status,
        }

        explanation = generate_explanation(code, meta.get("fund_name", code),
                                           metrics, risk_profile)

        results.append({
            "Fund Name":    meta.get("fund_name", code),
            "AMFI Code":    code,
            "Category":     meta.get("category", "Unknown"),
            "1Y Return":    row["return_1y"],
            "3Y Return":    row["return_3y"],
            "5Y Return":    row["return_5y"],
            "Volatility":   risk["volatility"],
            "Max Drawdown": risk["max_drawdown"],
            "Sharpe":       risk["sharpe"],
            "Sortino":      risk["sortino"],
            "Beta":         risk["beta"],
            "Alpha":        risk["alpha"],
            "Consistency":  risk["consistency"],
            "Score":        score,
            "Status":       status,
            "Breakdown":    breakdown,
            "Explanation":  explanation,
            "Invested":     meta.get("invested_amount", 0),
        })

    df = pd.DataFrame(results).sort_values("Score", ascending=False)

    # ── 5. Switch recommendations ─────────────────────────────────────────────
    recommendations = get_switch_recommendations(df, universe_df, risk_profile)

    # ── 6. Portfolio-level stats ──────────────────────────────────────────────
    portfolio_stats = _compute_portfolio_stats(df, funds, nav_df)

    return {
        "results":         results,
        "df":              df,
        "recommendations": recommendations,
        "risk_profile":    risk_profile,
        "portfolio_stats": portfolio_stats,
        "nav_df":          nav_df,
    }


def _compute_portfolio_stats(df: pd.DataFrame, funds: list, nav_df: pd.DataFrame) -> dict:
    """Aggregate portfolio-level metrics."""
    total_invested  = sum(f.get("invested_amount", 0) for f in funds)
    healthy_count   = (df["Status"] == "HEALTHY").sum()
    watch_count     = (df["Status"] == "WATCH").sum()
    review_count    = (df["Status"] == "REVIEW").sum()
    avg_score       = df["Score"].mean()

    # Weighted average 3Y return by invested amount
    rows_with_invest = []
    for _, row in df.iterrows():
        inv = row.get("Invested", 0) or 0
        r3  = row.get("3Y Return")
        if inv > 0 and r3 is not None:
            rows_with_invest.append((inv, r3))

    if rows_with_invest:
        total_w   = sum(w for w, _ in rows_with_invest)
        wtd_return = sum(w * r / total_w for w, r in rows_with_invest)
    else:
        wtd_return = None

    return {
        "total_invested":      total_invested,
        "num_funds":           len(df),
        "healthy_count":       int(healthy_count),
        "watch_count":         int(watch_count),
        "review_count":        int(review_count),
        "avg_score":           round(avg_score, 1),
        "weighted_return_3y":  round(wtd_return, 2) if wtd_return else None,
    }
