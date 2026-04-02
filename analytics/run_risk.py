from analytics.nav_loader import load_nav_for_portfolio
from analytics.risk import (
    calculate_volatility,
    calculate_max_drawdown,
    calculate_consistency
)

if __name__ == "__main__":
    nav_df = load_nav_for_portfolio()

    for amfi_code, group in nav_df.groupby("amfi_code"):
        vol = calculate_volatility(group)
        dd = calculate_max_drawdown(group)
        cons = calculate_consistency(group)

        print(f"\nFund: {amfi_code}")
        print(f"Volatility: {vol}%")
        print(f"Max Drawdown: {dd}%")
        print(f"Consistency: {cons}%")
        
if group["nav"].min() <= 0:
    print(f"⚠️ Invalid NAV detected in fund {amfi_code}")