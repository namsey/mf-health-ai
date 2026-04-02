from analytics.nav_loader import load_nav_for_portfolio
from analytics.returns import compute_fund_returns
from analytics.risk import (
    calculate_volatility,
    calculate_max_drawdown,
    calculate_consistency
)
from scoring.health_score import (
    score_returns,
    score_risk,
    get_fund_status
)
from ai.explain import generate_explanation


if __name__ == "__main__":
    nav_df = load_nav_for_portfolio()
    returns_df = compute_fund_returns(nav_df)

    for _, row in returns_df.iterrows():
        amfi_code = row["amfi_code"]

        group = nav_df[nav_df["amfi_code"] == amfi_code]

        vol = calculate_volatility(group)
        dd = calculate_max_drawdown(group)
        cons = calculate_consistency(group)

        ret_score = score_returns(row["return_1y"], row["return_3y"], row["return_5y"])
        risk_score = score_risk(vol, dd, cons)

        total_score = ret_score + risk_score
        status = get_fund_status(total_score)

        returns = {
            "return_1y": row["return_1y"],
            "return_3y": row["return_3y"],
            "return_5y": row["return_5y"]
        }

        explanation = generate_explanation(
            amfi_code,
            returns,
            vol,
            dd,
            cons,
            total_score,
            status
        )

        print("\n" + "="*50)
        print(f"Fund: {amfi_code}")
        print("-"*50)
        print(f"Score   : {total_score}")
        print(f"Status  : {status}")
        print("\nExplanation:")
        print(explanation)
        print("="*50)