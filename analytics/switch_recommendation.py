def get_best_fund(df):
    # Pick highest score fund
    best = df.sort_values(by="Score", ascending=False).iloc[0]
    return best


def get_switch_recommendations(df):
    recommendations = []

    best_fund = get_best_fund(df)

    for _, row in df.iterrows():
        if row["Status"] != "HEALTHY":

            # Avoid recommending same fund
            if row["Fund Name"] == best_fund["Fund Name"]:
                continue

            recommendations.append({
                "from_fund": row["Fund Name"],
                "to_fund": best_fund["Fund Name"],
                "reason": f"{best_fund['Fund Name']} has better score ({best_fund['Score']}) vs {row['Score']}"
            })

    return recommendations