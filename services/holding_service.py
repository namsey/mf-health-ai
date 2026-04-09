"""
services/holding_service.py
----------------------------
Analyses the investor's actual holdings:
  - Real P&L (current value vs total invested)
  - XIRR on actual cash flows
  - Health check on the held fund
  - Hold vs Switch recommendation with tax awareness

This is different from the portfolio health service which works on
hypothetical/tracked funds. This module works on funds the investor
ACTUALLY OWNS with their real purchase details.
"""

import logging
import pandas as pd
from typing import Optional
from datetime import datetime

from config.settings             import settings
from repository.holdings_repo    import get_all_holdings, compute_holding_summary
from repository.nav_repo         import load_nav
from analytics.returns           import calculate_cagr, calculate_xirr
from analytics.risk              import compute_all_risk_metrics
from scoring.health_score        import compute_total_score, get_fund_status, get_score_breakdown
from recommender.switch_advisor  import get_switch_recommendations
from ai.explain                  import generate_explanation
from fetchers.nav_history_api    import fetch_nav_history
from repository.nav_repo         import save_nav

logger = logging.getLogger(__name__)

# India LTCG threshold for equity funds: held > 1 year, gain > ₹1 lakh
LTCG_TAX_RATE   = 0.125   # 12.5 % post-2024 budget
STCG_TAX_RATE   = 0.20    # 20 % for < 1 year holding
LTCG_EXEMPTION  = 100_000  # ₹1 lakh exemption on LTCG


def analyse_all_holdings(portfolio_df: Optional[pd.DataFrame] = None) -> list[dict]:
    """
    Run full analysis on every holding the investor has recorded.

    Returns list of result dicts, one per held fund.
    """
    holdings = get_all_holdings()
    if not holdings:
        return []

    results = []
    for amfi_code, holding_data in holdings.items():
        result = analyse_single_holding(amfi_code, holding_data, portfolio_df)
        if result:
            results.append(result)

    # Sort: worst performing first (needs most attention)
    results.sort(key=lambda x: x["pnl_pct"])
    return results


def analyse_single_holding(amfi_code: str, holding_data: dict,
                            portfolio_df: Optional[pd.DataFrame] = None) -> Optional[dict]:
    """Full analysis for one held fund."""
    txns = holding_data.get("transactions", [])
    if not txns:
        return None

    # ── Ensure NAV data exists ────────────────────────────────────────────────
    nav_df = load_nav([amfi_code])
    if nav_df.empty:
        logger.info("Fetching NAV for held fund %s ...", amfi_code)
        fetched = fetch_nav_history(amfi_code)
        if fetched is not None:
            save_nav(fetched)
            nav_df = fetched
        else:
            logger.warning("Could not fetch NAV for %s", amfi_code)
            return None

    # ── Current NAV ───────────────────────────────────────────────────────────
    nav_sorted   = nav_df.sort_values("date")
    current_nav  = float(nav_sorted["nav"].iloc[-1])
    current_date = nav_sorted["date"].iloc[-1]
    fund_name    = holding_data.get("fund_name", amfi_code)

    # ── P&L summary ───────────────────────────────────────────────────────────
    summary = compute_holding_summary(amfi_code, current_nav)
    if not summary:
        return None

    # ── XIRR on actual cash flows ─────────────────────────────────────────────
    cashflows = []
    for t in txns:
        amt = t["amount"]
        if t["type"] in ("BUY", "SIP"):
            cashflows.append({"date": pd.Timestamp(t["date"]), "amount": -amt})
        elif t["type"] == "REDEEM":
            cashflows.append({"date": pd.Timestamp(t["date"]), "amount": amt})

    # Add current value as final positive cash flow
    if summary["total_units"] > 0:
        cashflows.append({"date": current_date, "amount": summary["current_value"]})

    xirr = calculate_xirr(cashflows)

    # ── Fund health metrics ───────────────────────────────────────────────────
    benchmark_df = load_nav([settings.nifty50_code])
    risk = compute_all_risk_metrics(nav_df, benchmark_df)

    r1 = calculate_cagr(nav_df, 1)
    r3 = calculate_cagr(nav_df, 3)
    r5 = calculate_cagr(nav_df, 5)

    score  = compute_total_score(r1, r3, r5, risk["sharpe"], risk["sortino"],
                                  risk["max_drawdown"], risk["consistency"])
    status = get_fund_status(score)
    breakdown = get_score_breakdown(r1, r3, r5, risk["sharpe"], risk["sortino"],
                                    risk["max_drawdown"], risk["consistency"])

    # ── Holding period & tax calculation ──────────────────────────────────────
    first_date     = pd.Timestamp(txns[0]["date"])
    holding_days   = (pd.Timestamp.now() - first_date).days
    is_long_term   = holding_days > 365
    tax_info       = _estimate_tax(summary["pnl"], is_long_term)

    # ── Hold / Switch recommendation ─────────────────────────────────────────
    recommendation = _build_recommendation(
        status, score, summary["pnl_pct"], xirr, is_long_term, tax_info, holding_days
    )

    # ── AI explanation ────────────────────────────────────────────────────────
    metrics_for_ai = {
        "return_1y": r1, "return_3y": r3, "return_5y": r5,
        **risk, "score": score, "status": status,
    }
    explanation = generate_explanation(amfi_code, fund_name, metrics_for_ai)

    return {
        # Identity
        "amfi_code":      amfi_code,
        "fund_name":      fund_name,

        # Holding summary
        "total_units":    summary["total_units"],
        "total_invested": summary["total_invested"],
        "current_value":  summary["current_value"],
        "current_nav":    current_nav,
        "avg_cost_nav":   summary["avg_cost_nav"],
        "pnl":            summary["pnl"],
        "pnl_pct":        summary["pnl_pct"],
        "xirr":           xirr,
        "holding_days":   holding_days,
        "is_long_term":   is_long_term,

        # Tax
        "tax_info":       tax_info,

        # Fund health
        "return_1y":      r1,
        "return_3y":      r3,
        "return_5y":      r5,
        **risk,
        "score":          score,
        "status":         status,
        "breakdown":      breakdown,

        # Advice
        "recommendation": recommendation,
        "explanation":    explanation,
        "transactions":   txns,
    }


def _estimate_tax(pnl: float, is_long_term: bool) -> dict:
    """Estimate capital gains tax (equity funds)."""
    if pnl <= 0:
        return {"tax": 0, "net_pnl": pnl, "note": "Loss — no tax liability"}

    if is_long_term:
        taxable = max(0, pnl - LTCG_EXEMPTION)
        tax     = round(taxable * LTCG_TAX_RATE, 2)
        note    = f"LTCG @ 12.5% on gains above ₹1 lakh exemption"
    else:
        tax  = round(pnl * STCG_TAX_RATE, 2)
        note = "STCG @ 20% (held < 1 year)"

    return {
        "tax":     tax,
        "net_pnl": round(pnl - tax, 2),
        "note":    note,
        "regime":  "LTCG" if is_long_term else "STCG",
    }


def _build_recommendation(status: str, score: float, pnl_pct: float,
                           xirr: Optional[float], is_long_term: bool,
                           tax_info: dict, holding_days: int) -> dict:
    """
    Generate a nuanced hold/switch/wait recommendation.
    Considers: fund health, your personal return, tax impact, holding period.
    """
    action = "HOLD"
    reasons = []
    cautions = []

    # Fund health signal
    if status == "HEALTHY":
        reasons.append(f"Fund health score is strong ({score}/100).")
    elif status == "WATCH":
        reasons.append(f"Fund health is weakening (score {score}/100). Monitor closely.")
        action = "MONITOR"
    else:
        reasons.append(f"Fund health is poor (score {score}/100).")
        action = "REVIEW_FOR_SWITCH"

    # Your personal return
    if xirr is not None:
        if xirr > 12:
            reasons.append(f"Your personal XIRR of {xirr:.1f}% is healthy.")
        elif xirr > 8:
            reasons.append(f"Your XIRR of {xirr:.1f}% is moderate.")
        else:
            reasons.append(f"Your XIRR of {xirr:.1f}% is below benchmark.")
            if action == "HOLD":
                action = "MONITOR"

    # Tax caution near 1-year boundary
    if 330 < holding_days < 365 and pnl_pct > 0:
        cautions.append(
            f"You are {365 - holding_days} days away from LTCG. "
            f"Waiting saves you ₹{round(tax_info['tax'] * (STCG_TAX_RATE - LTCG_TAX_RATE) / STCG_TAX_RATE):,.0f} in tax."
        )
        if action == "REVIEW_FOR_SWITCH":
            action = "WAIT_FOR_LTCG"

    # Tax liability on switch
    if action in ("REVIEW_FOR_SWITCH",) and tax_info["tax"] > 0:
        cautions.append(
            f"Switching will trigger ₹{tax_info['tax']:,.0f} in {tax_info['regime']} tax. "
            f"Ensure the alternative fund outperforms by enough to justify the cost."
        )

    return {
        "action":   action,
        "reasons":  reasons,
        "cautions": cautions,
    }
