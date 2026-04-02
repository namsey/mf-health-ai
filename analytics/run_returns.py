from analytics.nav_loader import load_nav_for_portfolio
from analytics.returns import compute_fund_returns

if __name__ == "__main__":
    nav_df = load_nav_for_portfolio()

    print(type(nav_df))        # should be DataFrame
    print(nav_df.head())       # sanity check

    returns_df = compute_fund_returns(nav_df)
    print(returns_df)
    print(nav_df["date"].min())
    print(nav_df["date"].max())