"""
config/settings.py
------------------
Single source of truth for all application settings.
All constants, paths, thresholds and external API config live here.
Never scatter magic numbers across modules.
"""

import os
import logging
from pathlib import Path
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()

# ── Directory layout ──────────────────────────────────────────────────────────
BASE_DIR  = Path(__file__).resolve().parent.parent
DATA_DIR  = BASE_DIR / "data"
CACHE_DIR = BASE_DIR / ".cache"
LOG_DIR   = BASE_DIR / "logs"

for d in (DATA_DIR, CACHE_DIR, LOG_DIR):
    d.mkdir(exist_ok=True)

# ── Logging setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "app.log"),
        logging.StreamHandler(),
    ],
)

# ── Settings dataclass ────────────────────────────────────────────────────────
@dataclass
class Settings:
    # Paths
    base_dir:        Path = BASE_DIR
    data_dir:        Path = DATA_DIR
    cache_dir:       Path = CACHE_DIR

    nav_cache_path:  Path = DATA_DIR  / "nav_history.csv"
    portfolio_path:  Path = DATA_DIR  / "portfolio.json"
    ai_cache_path:   Path = CACHE_DIR / "ai_responses.json"
    fund_list_path:  Path = DATA_DIR  / "fund_universe.json"

    # ── Financial constants (India) ───────────────────────────────────────────
    risk_free_rate: float = 0.065       # 10-yr India govt bond ~6.5 %
    trading_days:   int   = 252

    # ── External APIs ─────────────────────────────────────────────────────────
    amfi_nav_url:    str = "https://www.amfiindia.com/spages/NAVAll.txt"
    mfapi_base_url:  str = "https://api.mfapi.in/mf"

    # Nifty 50 proxy — HDFC Index Fund – Nifty 50 Plan (Direct)
    nifty50_code:    str = "120716"

    # ── OpenAI ────────────────────────────────────────────────────────────────
    openai_api_key:     str = os.getenv("OPENAI_API_KEY", "")
    openai_model:       str = "gpt-4o-mini"
    ai_cache_ttl_hours: int = 24          # Regen AI text once per day max

    # ── Scoring thresholds (out of 100) ───────────────────────────────────────
    healthy_threshold: int = 65
    watch_threshold:   int = 45

    # Scoring weights (must sum to 100)
    weight_return_5y:   int = 25
    weight_return_3y:   int = 20
    weight_sharpe:      int = 20
    weight_sortino:     int = 10
    weight_drawdown:    int = 15
    weight_consistency: int = 10

    # ── Fund categories ───────────────────────────────────────────────────────
    fund_categories: list = field(default_factory=lambda: [
        "Large Cap", "Mid Cap", "Small Cap", "Flexi Cap",
        "Multi Cap", "ELSS", "Debt", "Hybrid", "Index", "International",
    ])

    # HTTP request config
    request_timeout:  int = 30
    request_retries:  int = 3
    retry_backoff:    float = 1.5   # seconds


settings = Settings()
