"""
repository/nav_repo.py
-----------------------
All read/write operations for NAV time-series data.
Uses a CSV cache on disk; future upgrade path is TimescaleDB.
"""

import pandas as pd
import logging
from pathlib import Path
from typing import Optional

from config.settings import settings

logger = logging.getLogger(__name__)


def load_nav(amfi_codes: Optional[list[str]] = None) -> pd.DataFrame:
    """
    Load NAV data from disk cache.
    If amfi_codes provided, filter to those funds only.
    """
    path = settings.nav_cache_path
    if not path.exists():
        logger.warning("NAV cache not found at %s", path)
        return pd.DataFrame(columns=["amfi_code", "date", "nav"])

    df = pd.read_csv(path, parse_dates=["date"], dtype={"amfi_code": str})
    df = df[df["nav"] > 0].copy()
    df = df.sort_values(["amfi_code", "date"])

    if amfi_codes:
        codes = [str(c) for c in amfi_codes]
        df = df[df["amfi_code"].isin(codes)]
        missing = set(codes) - set(df["amfi_code"].unique())
        if missing:
            logger.warning("No NAV data found for codes: %s", missing)

    logger.info("Loaded %d NAV rows for %d funds", len(df), df["amfi_code"].nunique())
    return df


def save_nav(df: pd.DataFrame) -> None:
    """Append or overwrite NAV cache."""
    path = settings.nav_cache_path

    if path.exists():
        existing = pd.read_csv(path, parse_dates=["date"], dtype={"amfi_code": str})
        combined = pd.concat([existing, df], ignore_index=True)
        combined = combined.drop_duplicates(subset=["amfi_code", "date"]).sort_values(["amfi_code", "date"])
    else:
        combined = df

    combined.to_csv(path, index=False)
    logger.info("Saved %d NAV rows to cache", len(combined))


def get_latest_nav_date(amfi_code: str) -> Optional[pd.Timestamp]:
    """Return the latest date in cache for a given fund."""
    df = load_nav([amfi_code])
    if df.empty:
        return None
    return df["date"].max()


def is_cache_stale(amfi_code: str, max_age_days: int = 1) -> bool:
    """Return True if NAV data is older than max_age_days."""
    latest = get_latest_nav_date(amfi_code)
    if latest is None:
        return True
    age = (pd.Timestamp.now() - latest).days
    return age > max_age_days
