import requests
import pandas as pd
from pathlib import Path
from analytics.portfolio_loader import load_portfolio

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

def fetch_nav_history(amfi_code):
    url = f"https://api.mfapi.in/mf/{amfi_code}"
    response = requests.get(url)
    data = response.json()

    records = []
    for item in data["data"]:
        records.append({
            "amfi_code": amfi_code,
            "date": pd.to_datetime(item["date"], format="%d-%m-%Y"),
            "nav": float(item["nav"])
        })

    return pd.DataFrame(records)


def fetch_all_portfolio_nav():
    portfolio = load_portfolio()
    all_data = []

    for fund in portfolio:
        print(f"Fetching {fund['fund_name']}...")
        df = fetch_nav_history(fund["amfi_code"])
        all_data.append(df)

    final_df = pd.concat(all_data, ignore_index=True)

    output_path = DATA_DIR / "nav_history.csv"
    final_df.to_csv(output_path, index=False)

    print(f"Saved NAV history to {output_path}")


if __name__ == "__main__":
    fetch_all_portfolio_nav()