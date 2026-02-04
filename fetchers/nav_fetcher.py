import requests
import pandas as pd
from pathlib import Path
from datetime import datetime

AMFI_NAV_URL = "https://www.amfiindia.com/spages/NAVAll.txt"

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

NAV_CACHE = DATA_DIR / "nav_history.csv"

def fetch_nav_data():
    print("Downloading NAV data from AMFI...")
    response = requests.get(AMFI_NAV_URL, timeout=30)
    response.raise_for_status()

    records = []

    for line in response.text.splitlines():
        parts = line.split(";")

        if len(parts) < 6:
            continue

        scheme_code = parts[0].strip()
        scheme_name = parts[3].strip()
        nav_value = parts[4].strip()
        nav_date = parts[5].strip()

        if not scheme_code.isdigit():
            continue

        try:
            nav = float(nav_value)
            date = datetime.strptime(nav_date, "%d-%b-%Y")
        except ValueError:
            continue

        records.append({
            "amfi_code": scheme_code,
            "scheme_name": scheme_name,
            "nav": nav,
            "date": date
        })

    df = pd.DataFrame(records)
    return df


def save_nav_data(df):
    df.to_csv(NAV_CACHE, index=False)
    print(f"NAV data saved to {NAV_CACHE}")


if __name__ == "__main__":
    df = fetch_nav_data()
    save_nav_data(df)
    print(f"Total NAV records fetched: {len(df)}")
