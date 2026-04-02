import pandas as pd


def compute_daily_returns(df):
    df = df.sort_values("date").copy()

    # Remove invalid NAV values
    df = df[df["nav"] > 0]

    df["daily_return"] = df["nav"].pct_change()

    # Remove inf / NaN values
    df = df.replace([float("inf"), -float("inf")], None)
    df = df.dropna(subset=["daily_return"])

    return df


def calculate_volatility(df):
    df = compute_daily_returns(df)

    if df.empty:
        return None

    return round(df["daily_return"].std() * (252 ** 0.5) * 100, 2)


def calculate_max_drawdown(df):
    df = df.sort_values("date").copy()

    # Remove invalid NAV
    df = df[df["nav"] > 0]

    df["cum_max"] = df["nav"].cummax()
    df["drawdown"] = (df["nav"] - df["cum_max"]) / df["cum_max"]

    return round(df["drawdown"].min() * 100, 2)


def calculate_consistency(df):
    df = compute_daily_returns(df)

    valid_returns = df["daily_return"].dropna()

    if len(valid_returns) == 0:
        return None

    positive_days = (valid_returns > 0).sum()
    total_days = len(valid_returns)

    return round((positive_days / total_days) * 100, 2)