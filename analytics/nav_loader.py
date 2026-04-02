import pandas as pd
from pathlib import Path
from analytics.portfolio_loader import load_portfolio

BASE_DIR = Path(__file__).resolve().parent.parent
NAV_CACHE = BASE_DIR / "data" / "nav_history.csv"

def load_nav_for_portfolio():
    # Step 1: load your portfolio
    portfolio = load_portfolio()
    #amfi_codes = [f["amfi_code"] for f in portfolio]
    amfi_codes = [str(f["amfi_code"]) for f in portfolio]

    # Step 2: load NAV data
    #df = pd.read_csv(NAV_CACHE, parse_dates=["date"])
    df = pd.read_csv(NAV_CACHE, parse_dates=["date"], dtype={"amfi_code": str})

    # Step 3: filter only your funds
    df = df[df["amfi_code"].isin(amfi_codes)]

    return df