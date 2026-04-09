"""
services/data_refresh_service.py
---------------------------------
Handles all NAV data refresh operations.
In production this would be called by a scheduler (Celery / APScheduler).
For MVP it is triggered manually via the UI.
"""

import logging
import pandas as pd
from typing import Optional

from config.settings             import settings
from repository.portfolio_repo   import get_funds
from repository.nav_repo         import is_cache_stale, load_nav
from fetchers.nav_history_api    import fetch_and_save_funds

logger = logging.getLogger(__name__)


def refresh_portfolio_nav(force: bool = False) -> dict:
    """
    Refresh NAV for all portfolio funds + benchmark.
    force=True : always re-fetch regardless of cache age.
    """
    funds      = get_funds()
    all_codes  = [f["amfi_code"] for f in funds]
    all_codes.append(settings.nifty50_code)   # Benchmark

    if not force:
        stale_codes = [c for c in all_codes if is_cache_stale(c)]
        if not stale_codes:
            logger.info("All NAV data is fresh — skipping refresh")
            return {"status": "fresh", "refreshed": [], "failed": []}
    else:
        stale_codes = all_codes

    logger.info("Refreshing NAV for %d funds ...", len(stale_codes))
    results = fetch_and_save_funds(stale_codes)

    refreshed = [c for c, ok in results.items() if ok]
    failed    = [c for c, ok in results.items() if not ok]

    logger.info("Refresh complete. OK=%d  Failed=%d", len(refreshed), len(failed))
    return {"status": "done", "refreshed": refreshed, "failed": failed}


def get_nav_summary() -> dict:
    """Return metadata about cached NAV data."""
    funds      = get_funds()
    all_codes  = [f["amfi_code"] for f in funds] + [settings.nifty50_code]
    nav_df     = load_nav(all_codes)

    if nav_df.empty:
        return {"total_records": 0, "funds_cached": 0, "latest_date": None}

    return {
        "total_records": len(nav_df),
        "funds_cached":  nav_df["amfi_code"].nunique(),
        "latest_date":   str(nav_df["date"].max().date()),
        "earliest_date": str(nav_df["date"].min().date()),
    }
