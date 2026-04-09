"""
ai/explain.py
--------------
AI-powered fund health explanations with TTL file-based caching.

Cache design:
  Key  = "{amfi_code}:{date}"  (regenerate once per day at most)
  Store = JSON file at .cache/ai_responses.json
  TTL  = 24 hours (configurable in settings)

This prevents calling the AI API on every page reload — critical for
cost control when scaling to many users.
"""

import json
import logging
import hashlib
from datetime import datetime, timedelta
from typing import Optional

from openai import OpenAI
from config.settings import settings

logger = logging.getLogger(__name__)

# Lazy client — only instantiated when actually needed
_client: Optional[OpenAI] = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.openai_api_key)
    return _client


# ── Cache helpers ─────────────────────────────────────────────────────────────

def _cache_key(amfi_code: str) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    return f"{amfi_code}:{today}"


def _load_cache() -> dict:
    path = settings.ai_cache_path
    if not path.exists():
        return {}
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def _save_cache(cache: dict) -> None:
    with open(settings.ai_cache_path, "w") as f:
        json.dump(cache, f, indent=2)


def _get_cached(amfi_code: str) -> Optional[str]:
    cache = _load_cache()
    key   = _cache_key(amfi_code)
    entry = cache.get(key)
    if entry:
        logger.debug("AI cache HIT for %s", amfi_code)
        return entry["text"]
    return None


def _set_cached(amfi_code: str, text: str) -> None:
    cache = _load_cache()
    cache[_cache_key(amfi_code)] = {
        "text":       text,
        "generated":  datetime.now().isoformat(),
    }
    # Evict entries older than TTL to keep cache file small
    ttl_cutoff = datetime.now() - timedelta(hours=settings.ai_cache_ttl_hours * 2)
    cache = {
        k: v for k, v in cache.items()
        if datetime.fromisoformat(v["generated"]) > ttl_cutoff
    }
    _save_cache(cache)


# ── Main function ─────────────────────────────────────────────────────────────

def generate_explanation(amfi_code: str, fund_name: str, metrics: dict,
                         risk_profile: str = "moderate") -> str:
    """
    Generate a plain-English fund health explanation.
    Returns cached text if generated today, otherwise calls the API.
    """
    # Return from cache if available
    cached = _get_cached(amfi_code)
    if cached:
        return cached

    if not settings.openai_api_key:
        return _fallback_explanation(fund_name, metrics)

    prompt = _build_prompt(fund_name, metrics, risk_profile)

    try:
        client   = _get_client()
        response = client.chat.completions.create(
            model    = settings.openai_model,
            messages = [{"role": "user", "content": prompt}],
            max_tokens = 150,
            temperature = 0.4,
        )
        text = response.choices[0].message.content.strip()
        _set_cached(amfi_code, text)
        logger.info("AI explanation generated for %s", amfi_code)
        return text
    except Exception as exc:
        logger.error("OpenAI call failed for %s: %s", amfi_code, exc)
        return _fallback_explanation(fund_name, metrics)


def _build_prompt(fund_name: str, m: dict, risk_profile: str) -> str:
    def fmt(v, suffix=""):
        return f"{v}{suffix}" if v is not None else "N/A"

    return f"""
You are a SEBI-registered mutual fund research analyst writing for a retail investor
with {risk_profile} risk profile. Keep it under 100 words. Plain simple English.
Do NOT give buy/sell/hold advice. Just explain what the numbers mean in human terms.
Use ₹ symbol for Indian context. No asterisks or markdown.

Fund: {fund_name}
1Y CAGR: {fmt(m.get('return_1y'), '%')}
3Y CAGR: {fmt(m.get('return_3y'), '%')}
5Y CAGR: {fmt(m.get('return_5y'), '%')}
Sharpe Ratio: {fmt(m.get('sharpe'))}
Sortino Ratio: {fmt(m.get('sortino'))}
Annualised Volatility: {fmt(m.get('volatility'), '%')}
Max Drawdown: {fmt(m.get('max_drawdown'), '%')}
Consistency (positive days): {fmt(m.get('consistency'), '%')}
Alpha vs Nifty 50: {fmt(m.get('alpha'), '%')}
Beta: {fmt(m.get('beta'))}
Health Score: {m.get('score', 'N/A')}/100
Status: {m.get('status', 'N/A')}
""".strip()


def _fallback_explanation(fund_name: str, metrics: dict) -> str:
    """Rule-based fallback when AI is unavailable."""
    status = metrics.get("status", "UNKNOWN")
    r3     = metrics.get("return_3y")
    sharpe = metrics.get("sharpe")

    parts = [f"{fund_name} has a {status} health status."]

    if r3 is not None:
        if r3 >= 15:
            parts.append(f"It has delivered strong 3-year returns of {r3:.1f}%.")
        elif r3 >= 8:
            parts.append(f"Its 3-year returns of {r3:.1f}% are moderate.")
        else:
            parts.append(f"Its 3-year returns of {r3:.1f}% are below par.")

    if sharpe is not None:
        if sharpe >= 1.0:
            parts.append("Risk-adjusted performance (Sharpe) is good.")
        else:
            parts.append("Risk-adjusted performance (Sharpe) needs improvement.")

    return " ".join(parts)
