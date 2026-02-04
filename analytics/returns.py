import pandas as pd

def calculate_return(df, years):
    df = df.sort_values("date")
    latest_date = df["date"].max()
    target_date = latest_date - pd.DateOffset(years=years)

    past_df = df[df["date"] <= target_date]

    if past_df.empty:
        return None

    start_nav = past_df.iloc[-1]["nav"]
    end_nav = df.iloc[-1]["nav"]

    return round(((end_nav / start_nav) - 1) * 100, 2)

def compute_fund_returns(nav_df):
    results = []

    for amfi_code, group in nav_df.groupby("amfi_code"):
        returns = {
            "amfi_code": amfi_code,
            "return_1y": calculate_return(group, 1),
            "return_3y": calculate_return(group, 3),
            "return_5y": calculate_return(group, 5),
        }
        results.append(returns)

    return pd.DataFrame(results)
