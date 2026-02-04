import json
from pathlib import Path

PORTFOLIO_PATH = Path("data/portfolio.json")

REQUIRED_KEYS = {
    "fund_name",
    "amfi_code",
    "category",
    "invested_amount"
}

def load_portfolio():
    if not PORTFOLIO_PATH.exists():
        raise FileNotFoundError("portfolio.json not found")

    with open(PORTFOLIO_PATH, "r") as f:
        data = json.load(f)

    funds = data.get("funds", [])

    if not funds:
        raise ValueError("No funds found in portfolio")

    for idx, fund in enumerate(funds, start=1):
        missing = REQUIRED_KEYS - fund.keys()
        if missing:
            raise ValueError(
                f"Fund #{idx} missing keys: {missing}"
            )

    return funds


if __name__ == "__main__":
    funds = load_portfolio()
    print(f"Loaded {len(funds)} funds successfully:\n")
    for f in funds:
        print(f"- {f['fund_name']} ({f['amfi_code']})")
