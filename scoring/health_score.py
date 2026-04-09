"""
scoring/health_score.py
------------------------
Multi-factor weighted scoring engine.

Score breakdown (total = 100):
  5Y CAGR        25 pts   — long-term compounding ability
  3Y CAGR        20 pts   — medium-term consistency
  Sharpe Ratio   20 pts   — risk-adjusted returns
  Sortino Ratio  10 pts   — downside protection
  Max Drawdown   15 pts   — worst-case loss resilience
  Consistency    10 pts   — day-to-day positive momentum

Status:
  HEALTHY   >= 65
  WATCH     45–64
  REVIEW    < 45
"""

from typing import Optional
from config.settings import settings


def _safe(val: Optional[float], fallback: float = 0.0) -> float:
    return float(val) if val is not None else fallback


def score_return_5y(r5: Optional[float]) -> float:
    """25 pts max — long-term CAGR."""
    r = _safe(r5)
    if r >= 18:   return 25
    if r >= 14:   return 20
    if r >= 10:   return 15
    if r >= 6:    return 10
    if r >= 0:    return 5
    return 0


def score_return_3y(r3: Optional[float]) -> float:
    """20 pts max — medium-term CAGR."""
    r = _safe(r3)
    if r >= 20:   return 20
    if r >= 15:   return 16
    if r >= 10:   return 12
    if r >= 5:    return 8
    if r >= 0:    return 4
    return 0


def score_sharpe(sharpe: Optional[float]) -> float:
    """20 pts max — Sharpe Ratio."""
    s = _safe(sharpe)
    if s >= 1.5:  return 20
    if s >= 1.0:  return 16
    if s >= 0.5:  return 12
    if s >= 0.0:  return 6
    return 0


def score_sortino(sortino: Optional[float]) -> float:
    """10 pts max — Sortino Ratio."""
    s = _safe(sortino)
    if s >= 2.0:  return 10
    if s >= 1.5:  return 8
    if s >= 1.0:  return 6
    if s >= 0.5:  return 4
    if s >= 0.0:  return 2
    return 0


def score_drawdown(dd: Optional[float]) -> float:
    """15 pts max — lower drawdown = better."""
    d = _safe(dd)   # negative value e.g. -18.5
    if d >= -15:    return 15
    if d >= -20:    return 12
    if d >= -30:    return 8
    if d >= -40:    return 4
    return 0


def score_consistency(cons: Optional[float]) -> float:
    """10 pts max — % of positive return days."""
    c = _safe(cons)
    if c >= 58:   return 10
    if c >= 55:   return 8
    if c >= 52:   return 6
    if c >= 50:   return 4
    if c >= 45:   return 2
    return 0


def compute_total_score(r1: Optional[float], r3: Optional[float],
                        r5: Optional[float], sharpe: Optional[float],
                        sortino: Optional[float], drawdown: Optional[float],
                        consistency: Optional[float]) -> float:
    """Compute aggregate score (0–100)."""
    return round(
        score_return_5y(r5)
        + score_return_3y(r3)
        + score_sharpe(sharpe)
        + score_sortino(sortino)
        + score_drawdown(drawdown)
        + score_consistency(consistency),
        1
    )


def get_fund_status(score: float) -> str:
    if score >= settings.healthy_threshold:
        return "HEALTHY"
    if score >= settings.watch_threshold:
        return "WATCH"
    return "REVIEW"


def get_score_breakdown(r1, r3, r5, sharpe, sortino, drawdown, consistency) -> dict:
    """Return itemised score for display."""
    return {
        "5Y Return":    score_return_5y(r5),
        "3Y Return":    score_return_3y(r3),
        "Sharpe":       score_sharpe(sharpe),
        "Sortino":      score_sortino(sortino),
        "Drawdown":     score_drawdown(drawdown),
        "Consistency":  score_consistency(consistency),
    }
