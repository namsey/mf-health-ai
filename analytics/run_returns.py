from analytics.portfolio_loader import load_portfolio
from analytics.returns import compute_fund_returns

if __name__ == "__main__":
    nav_df = load_portfolio()
    returns_df = compute_fund_returns(nav_df)
    print(returns_df)
