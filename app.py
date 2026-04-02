import streamlit as st
import pandas as pd

from analytics.switch_recommendation import get_switch_recommendations
from analytics.nav_loader import load_nav_for_portfolio
from analytics.returns import compute_fund_returns

from analytics.portfolio_loader import load_portfolio

portfolio = load_portfolio()
code_to_name = {f["amfi_code"]: f["fund_name"] for f in portfolio}

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

# ------------------ PAGE CONFIG ------------------
st.set_page_config(page_title="MF Health Dashboard", layout="wide")

st.title("📊 Mutual Fund Health Dashboard")

# ------------------ LOAD DATA ------------------
nav_df = load_nav_for_portfolio()
returns_df = compute_fund_returns(nav_df)

results = []

# ------------------ PROCESS DATA ------------------
for _, row in returns_df.iterrows():
    amfi_code = row["amfi_code"]
    group = nav_df[nav_df["amfi_code"] == amfi_code]

    #fund_name = group["scheme_name"].iloc[0]  # ✅ Improvement 1
    fund_name = code_to_name.get(amfi_code, amfi_code)

    vol = calculate_volatility(group)
    dd = calculate_max_drawdown(group)
    cons = calculate_consistency(group)

    ret_score = score_returns(row["return_1y"], row["return_3y"], row["return_5y"])
    risk_score = score_risk(vol, dd, cons)

    total_score = ret_score + risk_score
    status = get_fund_status(total_score)

    results.append({
        "Fund Name": fund_name,
        "AMFI Code": amfi_code,
        "1Y Return": row["return_1y"],
        "3Y Return": row["return_3y"],
        "5Y Return": row["return_5y"],
        "Volatility": vol,
        "Drawdown": dd,
        "Consistency": cons,
        "Score": total_score,
        "Status": status
    })

df = pd.DataFrame(results)

# ------------------ IMPROVEMENT 5: SORT ------------------
df = df.sort_values(by="Score")  # worst fund first

# ------------------ SWITCH RECOMMENDATIONS ------------------
st.subheader("🔁 Suggested Switches")

recommendations = get_switch_recommendations(df)

if not recommendations:
    st.success("✅ All your funds are healthy. No switch needed.")
else:
    for rec in recommendations:
        st.warning(f"""
        🔄 Switch Suggestion:

        **From:** {rec['from_fund']}  
        **To:** {rec['to_fund']}  

        📊 Reason: {rec['reason']}
        """)

# ------------------ TABLE ------------------
st.subheader("📋 Portfolio Overview")
st.dataframe(df, use_container_width=True)

# ------------------ FILTER ------------------
status_filter = st.selectbox(
    "Filter by Status",
    ["ALL", "HEALTHY", "WATCH", "REVIEW"]
)

# ------------------ FUND INSIGHTS ------------------
st.subheader("🔍 Fund Insights")

for _, row in df.iterrows():

    if status_filter != "ALL" and row["Status"] != status_filter:
        continue

    group = nav_df[nav_df["amfi_code"] == row["AMFI Code"]]

    st.markdown(f"## 📌 {row['Fund Name']}")

    # ------------------ IMPROVEMENT 3: KEY METRICS ------------------
    col1, col2, col3 = st.columns(3)
    col1.metric("1Y Return", f"{row['1Y Return']}%")
    col2.metric("Volatility", f"{row['Volatility']}%")
    col3.metric("Drawdown", f"{row['Drawdown']}%")

    # ------------------ IMPROVEMENT 2: CLEAN CHART ------------------
    st.line_chart(
    group.set_index("date")["nav"],
    width="stretch"
   )

    # ------------------ SCORE + STATUS ------------------
    col1, col2 = st.columns(2)
    col1.metric("Score", row["Score"])
    col2.metric("Status", row["Status"])

    # ------------------ IMPROVEMENT 4: ALERT ------------------
    if row["Status"] == "HEALTHY":
        st.success("Strong fund. No action needed.")
    elif row["Status"] == "WATCH":
        st.warning("⚠️ Monitor performance closely.")
    else:
        st.error("🚨 Consider reviewing or switching.")

    if row["Status"] != "HEALTHY":
        st.warning("⚠️ Attention needed for this fund")

    # ------------------ AI EXPLANATION ------------------
    returns = {
        "return_1y": row["1Y Return"],
        "return_3y": row["3Y Return"],
        "return_5y": row["5Y Return"]
    }

    explanation = generate_explanation(
        row["AMFI Code"],
        returns,
        row["Volatility"],
        row["Drawdown"],
        row["Consistency"],
        row["Score"],
        row["Status"]
    )

    st.info(explanation)

    st.divider()