"""
repository/portfolio_repo.py
-----------------------------
Repository pattern: all portfolio read/write operations live here.
Business logic never touches files directly — it calls this module.
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

from config.settings import settings

logger = logging.getLogger(__name__)

REQUIRED_KEYS = {"fund_name", "amfi_code", "category", "invested_amount"}

_DEFAULT_PORTFOLIO = {
    "owner": "personal",
    "risk_profile": "moderate",   # conservative | moderate | aggressive
    "base_currency": "INR",
    "created_at": datetime.now().isoformat(),
    "funds": []
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_raw() -> dict:
    path = settings.portfolio_path
    if not path.exists():
        logger.info("portfolio.json not found — creating empty portfolio")
        _save_raw(_DEFAULT_PORTFOLIO)
        return _DEFAULT_PORTFOLIO
    with open(path) as f:
        return json.load(f)


def _save_raw(data: dict) -> None:
    with open(settings.portfolio_path, "w") as f:
        json.dump(data, f, indent=2)


# ── Public API ────────────────────────────────────────────────────────────────

def get_portfolio() -> dict:
    """Return the full portfolio dict."""
    return _load_raw()


def get_funds() -> list[dict]:
    """Return list of fund dicts."""
    data = _load_raw()
    funds = data.get("funds", [])
    for idx, fund in enumerate(funds, 1):
        missing = REQUIRED_KEYS - fund.keys()
        if missing:
            raise ValueError(f"Fund #{idx} '{fund.get('fund_name')}' missing keys: {missing}")
    return funds


def get_risk_profile() -> str:
    return _load_raw().get("risk_profile", "moderate")


def set_risk_profile(profile: str) -> None:
    allowed = {"conservative", "moderate", "aggressive"}
    if profile not in allowed:
        raise ValueError(f"risk_profile must be one of {allowed}")
    data = _load_raw()
    data["risk_profile"] = profile
    _save_raw(data)
    logger.info("Risk profile updated → %s", profile)


def add_fund(fund: dict) -> None:
    """Add a fund to the portfolio. Validates required keys."""
    missing = REQUIRED_KEYS - fund.keys()
    if missing:
        raise ValueError(f"Fund missing keys: {missing}")

    data = _load_raw()
    existing_codes = {f["amfi_code"] for f in data["funds"]}
    if fund["amfi_code"] in existing_codes:
        raise ValueError(f"Fund {fund['amfi_code']} already exists in portfolio")

    fund.setdefault("sip_amount", 0)
    fund.setdefault("purchase_date", datetime.now().strftime("%Y-%m-%d"))
    data["funds"].append(fund)
    _save_raw(data)
    logger.info("Added fund: %s (%s)", fund["fund_name"], fund["amfi_code"])


def remove_fund(amfi_code: str) -> bool:
    """Remove a fund by amfi_code. Returns True if removed."""
    data = _load_raw()
    before = len(data["funds"])
    data["funds"] = [f for f in data["funds"] if f["amfi_code"] != amfi_code]
    if len(data["funds"]) == before:
        return False
    _save_raw(data)
    logger.info("Removed fund: %s", amfi_code)
    return True


def update_fund(amfi_code: str, updates: dict) -> bool:
    """Update fields of an existing fund."""
    data = _load_raw()
    for fund in data["funds"]:
        if fund["amfi_code"] == amfi_code:
            fund.update(updates)
            _save_raw(data)
            return True
    return False
