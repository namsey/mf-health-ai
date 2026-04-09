"""
fetchers/nav_history_api.py
----------------------------
Fetches full historical NAV data from mfapi.in with retry logic.
Respects rate limits. Designed to be called by the data refresh service.
"""

import time
import logging
import requests
import pandas as pd
from typing import Optional

from config.settings import settings
from repository.nav_repo import save_nav

logger = logging.getLogger(__name__)


def _get_with_retry(url: str) -> Optional[dict]:
    """GET with exponential backoff retry."""
    delay = settings.retry_backoff
    for attempt in range(1, settings.request_retries + 1):
        try:
            resp = requests.get(url, timeout=settings.request_timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            logger.warning("Attempt %d/%d failed for %s: %s",
                           attempt, settings.request_retries, url, exc)
            if attempt < settings.request_retries:
                time.sleep(delay)
                delay *= 2
    logger.error("All retries exhausted for %s", url)
    return None


def fetch_nav_history(amfi_code: str) -> Optional[pd.DataFrame]:
    """
    Fetch complete NAV history for one fund from mfapi.in.
    Returns a DataFrame with columns: amfi_code, date, nav
    """
    url = f"{settings.mfapi_base_url}/{amfi_code}"
    data = _get_with_retry(url)

    if not data or "data" not in data:
        logger.error("Invalid response for fund %s", amfi_code)
        return None

    records = []
    for item in data["data"]:
        try:
            records.append({
                "amfi_code": str(amfi_code),
                "date":      pd.to_datetime(item["date"], format="%d-%m-%Y"),
                "nav":       float(item["nav"]),
            })
        except (KeyError, ValueError):
            continue

    if not records:
        logger.warning("No valid NAV records for %s", amfi_code)
        return None

    df = pd.DataFrame(records)
    logger.info("Fetched %d NAV rows for %s", len(df), amfi_code)
    return df


def fetch_and_save_funds(amfi_codes: list[str]) -> dict:
    """
    Fetch NAV history for multiple funds and save to cache.
    Returns {amfi_code: success_bool}
    """
    results = {}
    for code in amfi_codes:
        logger.info("Fetching NAV for %s ...", code)
        df = fetch_nav_history(code)
        if df is not None:
            save_nav(df)
            results[code] = True
        else:
            results[code] = False
        time.sleep(0.3)   # Be polite to the API

    success = sum(results.values())
    logger.info("Fetched %d/%d funds successfully", success, len(amfi_codes))
    return results
