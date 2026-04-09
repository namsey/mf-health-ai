"""
app.py
-------
Streamlit entry point. This file only handles UI rendering.
All business logic is in the services layer.

Tabs:
  📊 Portfolio Health   — fund health scores, metrics, AI insights
  🔁 Switch Advisor     — category-aware switch recommendations
  🌐 Fund Discovery     — search best funds in a category
  📈 Analytics          — detailed charts and comparisons
  ⚙️  Settings           — manage portfolio, risk profile, refresh data
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

from config.settings import settings

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="MF Health AI",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Style ─────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.metric-card {
    background: #f8f9fa; border-radius: 10px; padding: 16px 20px;
    border-left: 4px solid #0066cc;
}
.status-healthy { color: #22863a; font-weight: 700; }
.status-watch   { color: #b08800; font-weight: 700; }
.status-review  { color: #c0392b; font-weight: 700; }
.disclaimer {
    background: #fff8e1; padding: 10px 16px; border-radius: 6px;
    font-size: 0.8em; color: #7d6608; margin-top: 8px;
}
</style>
""", unsafe_allow_html=True)

# ── Disclaimer (always visible) ───────────────────────────────────────────────
st.markdown("""
<div class="disclaimer">
⚠️ <b>Disclaimer:</b> This tool provides analytical insights for informational purposes only.
It is <b>not</b> SEBI-registered investment advice. Past performance does not guarantee future returns.
Consult a SEBI-registered investment advisor before making investment decisions.
</div>
""", unsafe_allow_html=True)

st.title("📊 Mutual Fund Health AI")

# ── Format helpers (defined early — used in all tabs) ─────────────────────────
def _fmt_pct(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "N/A"
    return f"{v:.1f}%"


def _fmt_num(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "N/A"
    return f"{v:.2f}"



# ── Load data (cached for this session) ──────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def _run_health():
    from services.health_service import run_portfolio_health
    return run_portfolio_health(universe_df=None)


@st.cache_data(ttl=3600, show_spinner=False)
def _get_nav_summary():
    from services.data_refresh_service import get_nav_summary
    return get_nav_summary()


# ── Status colour helper ──────────────────────────────────────────────────────
STATUS_COLOUR = {"HEALTHY": "🟢", "WATCH": "🟡", "REVIEW": "🔴"}
STATUS_CSS    = {"HEALTHY": "status-healthy", "WATCH": "status-watch", "REVIEW": "status-review"}


def status_badge(status: str) -> str:
    return f"{STATUS_COLOUR.get(status, '')} {status}"


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN TABS
# ═══════════════════════════════════════════════════════════════════════════════

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📊 Portfolio Health",
    "🔁 Switch Advisor",
    "💼 My Holdings",
    "📈 Analytics",
    "🌐 Fund Discovery",
    "⚙️ Settings",
])

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — PORTFOLIO HEALTH
# ═══════════════════════════════════════════════════════════════════════════════
with tab1:
    with st.spinner("Analysing your portfolio …"):
        result = _run_health()

    if "error" in result:
        st.error(result["error"])
        st.info("👉 Go to **Settings** tab → click **Refresh NAV Data** to fetch latest data.")
        st.stop()

    df   = result["df"]
    stats = result["portfolio_stats"]

    # ── Portfolio summary bar ─────────────────────────────────────────────────
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Invested", f"₹{stats['total_invested']:,.0f}")
    c2.metric("Funds", stats["num_funds"])
    c3.metric("Avg Score", f"{stats['avg_score']}/100")
    c4.metric("Weighted 3Y CAGR",
              f"{stats['weighted_return_3y']}%" if stats['weighted_return_3y'] else "N/A")
    with c5:
        healthy = stats["healthy_count"]
        watch   = stats["watch_count"]
        review  = stats["review_count"]
        st.markdown(f"🟢 **{healthy}** Healthy &nbsp; 🟡 **{watch}** Watch &nbsp; 🔴 **{review}** Review")

    st.divider()

    # ── Filter ────────────────────────────────────────────────────────────────
    col_l, col_r = st.columns([2, 1])
    with col_l:
        status_filter = st.radio(
            "Show funds:", ["ALL", "HEALTHY", "WATCH", "REVIEW"],
            horizontal=True, key="status_filter"
        )
    with col_r:
        sort_col = st.selectbox("Sort by", ["Score", "3Y Return", "5Y Return", "Sharpe", "Volatility"])

    filtered = df if status_filter == "ALL" else df[df["Status"] == status_filter]
    filtered = filtered.sort_values(sort_col, ascending=False if sort_col != "Volatility" else True)

    # ── Fund cards ────────────────────────────────────────────────────────────
    for _, row in filtered.iterrows():
        with st.expander(
            f"{STATUS_COLOUR.get(row['Status'], '')}  **{row['Fund Name']}**  "
            f"— Score {row['Score']}/100  |  {row['Category']}",
            expanded=False
        ):
            # Key metrics row
            m1, m2, m3, m4, m5, m6 = st.columns(6)
            m1.metric("1Y CAGR",     _fmt_pct(row["1Y Return"]))
            m2.metric("3Y CAGR",     _fmt_pct(row["3Y Return"]))
            m3.metric("5Y CAGR",     _fmt_pct(row["5Y Return"]))
            m4.metric("Sharpe",      _fmt_num(row["Sharpe"]))
            m5.metric("Volatility",  _fmt_pct(row["Volatility"]))
            m6.metric("Max Drawdown",_fmt_pct(row["Max Drawdown"]))

            col_a, col_b = st.columns([3, 1])

            with col_a:
                # Score breakdown bar chart
                bd = row.get("Breakdown", {})
                if bd:
                    bd_df = pd.DataFrame({
                        "Metric": list(bd.keys()),
                        "Score":  list(bd.values()),
                        "Max":    [25, 20, 20, 10, 15, 10],
                    })
                    bd_df["Unused"] = bd_df["Max"] - bd_df["Score"]
                    fig = go.Figure()
                    fig.add_bar(name="Scored", x=bd_df["Metric"], y=bd_df["Score"],
                                marker_color="#0066cc")
                    fig.add_bar(name="Remaining", x=bd_df["Metric"], y=bd_df["Unused"],
                                marker_color="#e8ecf0")
                    fig.update_layout(
                        barmode="stack", height=220,
                        margin=dict(l=0, r=0, t=20, b=0),
                        showlegend=False,
                        plot_bgcolor="rgba(0,0,0,0)",
                        paper_bgcolor="rgba(0,0,0,0)",
                        yaxis=dict(range=[0, 25]),
                    )
                    st.plotly_chart(fig, use_container_width=True)

            with col_b:
                st.markdown(f"**Status:** {status_badge(row['Status'])}")
                st.markdown(f"**Alpha:** {_fmt_pct(row.get('Alpha'))}")
                st.markdown(f"**Beta:** {_fmt_num(row.get('Beta'))}")
                st.markdown(f"**Sortino:** {_fmt_num(row.get('Sortino'))}")
                st.markdown(f"**Consistency:** {_fmt_pct(row.get('Consistency'))}")

            # AI explanation
            if row.get("Explanation"):
                st.info(f"💡 {row['Explanation']}")

            # Alert badges
            if row["Status"] == "HEALTHY":
                st.success("✅ Strong fund. Metrics are within healthy range.")
            elif row["Status"] == "WATCH":
                st.warning("⚠️ Monitor this fund closely. Some metrics are weakening.")
            else:
                st.error("🚨 This fund needs attention. Review and consider alternatives.")


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — SWITCH ADVISOR
# ═══════════════════════════════════════════════════════════════════════════════
with tab2:
    result = _run_health()
    if "error" in result:
        st.error(result["error"])
        st.stop()

    recs = result["recommendations"]
    st.subheader("🔁 Category-Aware Switch Recommendations")
    st.caption(
        "Switches are only suggested within the same fund category "
        "and only when the score improvement is ≥ 10 points."
    )

    if not recs:
        st.success("✅ All your funds are healthy or no better alternative exists in the same category.")
    else:
        for rec in recs:
            with st.container():
                st.markdown(f"""
**Switch from:** {rec['from_fund']} (Score: {rec['from_score']}) — _{rec['from_status']}_
→
**Switch to:** {rec['to_fund']} (Score: {rec['to_score']}) — 🟢 HEALTHY
**Category:** {rec['category']} &nbsp;|&nbsp; **Score gain:** +{rec['score_gain']} pts
""")
                for r in rec["reasons"]:
                    st.markdown(f"  • {r}")
                st.divider()

    st.markdown("""
<div class="disclaimer">
Consult a SEBI-registered investment advisor before switching funds.
Exit loads and tax implications (STCG/LTCG) apply.
</div>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — ANALYTICS
# ═══════════════════════════════════════════════════════════════════════════════
with tab3:
    # ═══════════════════════════════════════════════════════════════════════
    # TAB 3 — MY HOLDINGS (actual purchased funds)
    # ═══════════════════════════════════════════════════════════════════════
    st.subheader("💼 My Holdings — Funds I Actually Own")
    st.caption(
        "Enter the mutual funds you have purchased. "
        "The app calculates your real P&L, XIRR on your actual cash flows, "
        "checks fund health, and tells you whether to hold or switch."
    )

    from repository.holdings_repo import (
        get_all_holdings, add_transaction, remove_holding,
        remove_transaction, compute_holding_summary
    )
    from repository.nav_repo import load_nav
    from services.holding_service import analyse_all_holdings

    ACTION_COLOUR = {
        "HOLD":              "🟢",
        "MONITOR":           "🟡",
        "REVIEW_FOR_SWITCH": "🔴",
        "WAIT_FOR_LTCG":     "🔵",
    }

    # ── CAS PDF import ────────────────────────────────────────────────────
    with st.expander("📄 Import from CAS PDF (CAMS / KFintech statement)", expanded=False):
        st.markdown("""
**How to get your CAS:**
1. Go to [camsonline.com](https://www.camsonline.com/Investors/Statements/Consolidated-Account-Statement) or [kfintech.com](https://mfs.kfintech.com/investor/General/ConsolidatedAccountStatement)
2. Enter your email and PAN → they email you a PDF within minutes
3. Password = **PAN (uppercase) + Date of birth** (e.g. `ABCDE1234F01011990`)
""")
        cas_file = st.file_uploader("Upload CAS PDF", type=["pdf"], key="cas_upload")
        cas_pwd  = st.text_input("PDF Password", type="password", key="cas_pwd",
                                  placeholder="e.g. ABCDE1234F01011990")
        if st.button("Parse CAS PDF") and cas_file:
            with st.spinner("Parsing your CAS statement …"):
                from fetchers.cas_parser import parse_cas_pdf
                parsed = parse_cas_pdf(cas_file.read(), password=cas_pwd)

            if not parsed or not parsed.get("holdings"):
                st.error("Could not parse the PDF. Check the password and try again.")
            else:
                st.success(f"Found {len(parsed['holdings'])} holdings for {parsed.get('investor_name')}")
                st.caption("Review the parsed holdings below. Map the AMFI code manually and click Save.")

                for i, h in enumerate(parsed["holdings"]):
                    with st.expander(f"{h['fund_name']} — Folio {h['folio']}"):
                        c1, c2, c3 = st.columns(3)
                        c1.metric("Units", h["units"])
                        c2.metric("Current NAV", h["nav"])
                        c3.metric("Value", f"₹{h['value']:,.0f}")
                        amfi_for_cas = st.text_input(
                            "Enter AMFI code for this fund",
                            key=f"cas_amfi_{i}",
                            help="Find at mfapi.in — needed to fetch historical NAV"
                        )
                        if st.button("Save this holding", key=f"cas_save_{i}") and amfi_for_cas:
                            for txn in h["transactions"]:
                                add_transaction(
                                    amfi_for_cas, txn["date"], txn["type"],
                                    txn["units"], txn["nav"]
                                )
                            st.success("Saved! Transactions imported.")
                            st.rerun()

    st.divider()

    # ── Add holding manually ──────────────────────────────────────────────
    with st.expander("➕ Add / Record a Purchase", expanded=False):
        with st.form("add_holding_form"):
            st.markdown("**Fund details**")
            hf_code  = st.text_input("AMFI Code", placeholder="e.g. 122639")
            hf_name  = st.text_input("Fund Name", placeholder="e.g. Parag Parikh Flexi Cap")
            st.markdown("**Transaction details**")
            hf_type  = st.selectbox("Transaction Type", ["BUY", "SIP", "REDEEM"])
            hf_date  = st.date_input("Date of Purchase")
            hf_units = st.number_input("Units Purchased", min_value=0.0, step=0.001, format="%.3f")
            hf_nav   = st.number_input("NAV on Purchase Date (₹)", min_value=0.0, step=0.01)

            if st.form_submit_button("Record Transaction"):
                if not hf_code or hf_units <= 0 or hf_nav <= 0:
                    st.error("Please fill all fields with valid values.")
                else:
                    add_transaction(hf_code.strip(), str(hf_date), hf_type, hf_units, hf_nav)
                    # Store fund name in holdings data
                    from repository.holdings_repo import _load, _save
                    d = _load()
                    if hf_code in d:
                        d[hf_code]["fund_name"] = hf_name
                        _save(d)
                    st.success(f"Transaction recorded for {hf_name or hf_code}")
                    st.rerun()

    st.divider()

    # ── Analyse all holdings ──────────────────────────────────────────────
    holdings_raw = get_all_holdings()
    if not holdings_raw:
        st.info("No holdings recorded yet. Add a purchase above or import your CAS PDF.")
    else:
        with st.spinner("Analysing your holdings …"):
            analyses = analyse_all_holdings()

        if not analyses:
            st.warning("Could not fetch NAV data for your holdings. Check your internet connection.")
        else:
            # ── Portfolio P&L summary ──────────────────────────────────────
            total_inv = sum(a["total_invested"] for a in analyses)
            total_val = sum(a["current_value"]  for a in analyses)
            total_pnl = total_val - total_inv
            pnl_pct   = (total_pnl / total_inv * 100) if total_inv > 0 else 0

            sc1, sc2, sc3, sc4 = st.columns(4)
            sc1.metric("Total Invested",   f"₹{total_inv:,.0f}")
            sc2.metric("Current Value",    f"₹{total_val:,.0f}")
            sc3.metric("Overall P&L",      f"₹{total_pnl:,.0f}",
                        delta=f"{pnl_pct:+.1f}%")
            sc4.metric("Funds Analysed",   len(analyses))

            st.divider()

            # ── Individual fund cards ──────────────────────────────────────
            for a in analyses:
                rec    = a["recommendation"]
                action = rec["action"]
                icon   = ACTION_COLOUR.get(action, "⚪")

                with st.expander(
                    f"{icon} **{a['fund_name']}**  |  "
                    f"P&L: ₹{a['pnl']:+,.0f} ({a['pnl_pct']:+.1f}%)  |  "
                    f"XIRR: {a['xirr']:.1f}%" if a['xirr'] else
                    f"{icon} **{a['fund_name']}**  |  P&L: ₹{a['pnl']:+,.0f} ({a['pnl_pct']:+.1f}%)",
                    expanded=True
                ):
                    m1, m2, m3, m4, m5, m6 = st.columns(6)
                    m1.metric("Invested",      f"₹{a['total_invested']:,.0f}")
                    m2.metric("Current Value", f"₹{a['current_value']:,.0f}")
                    m3.metric("Units Held",    f"{a['total_units']:.3f}")
                    m4.metric("Avg Cost NAV",  f"₹{a['avg_cost_nav']:.2f}")
                    m5.metric("Current NAV",   f"₹{a['current_nav']:.2f}")
                    m6.metric("XIRR",          f"{a['xirr']:.1f}%" if a['xirr'] else "N/A")

                    st.divider()
                    col_l, col_r = st.columns([3, 2])

                    with col_l:
                        # Fund health metrics
                        st.markdown("**Fund health metrics**")
                        hm1, hm2, hm3 = st.columns(3)
                        hm1.metric("3Y CAGR",    _fmt_pct(a["return_3y"]))
                        hm2.metric("Sharpe",     _fmt_num(a["sharpe"]))
                        hm3.metric("Drawdown",   _fmt_pct(a["max_drawdown"]))
                        st.markdown(f"**Health score:** {a['score']}/100 — {status_badge(a['status'])}")

                    with col_r:
                        # Recommendation box
                        st.markdown("**Recommendation**")
                        action_labels = {
                            "HOLD":              "Hold — fund is performing well",
                            "MONITOR":           "Monitor — watch for further decline",
                            "REVIEW_FOR_SWITCH": "Review for switch — consider alternatives",
                            "WAIT_FOR_LTCG":     "Wait for LTCG — switching too early costs tax",
                        }
                        action_colors = {
                            "HOLD": "success", "MONITOR": "warning",
                            "REVIEW_FOR_SWITCH": "error", "WAIT_FOR_LTCG": "info"
                        }
                        getattr(st, action_colors.get(action, "info"))(
                            f"{icon} **{action_labels.get(action, action)}**"
                        )
                        for r in rec["reasons"]:
                            st.write(f"• {r}")
                        for c in rec["cautions"]:
                            st.warning(f"⚠️ {c}")

                    # Tax info
                    tax = a["tax_info"]
                    with st.expander("💰 Tax estimate (equity funds)", expanded=False):
                        tc1, tc2, tc3 = st.columns(3)
                        tc1.metric("Holding period", f"{a['holding_days']} days")
                        tc2.metric("Tax regime", tax.get("regime", "N/A"))
                        tc3.metric("Est. tax", f"₹{tax['tax']:,.0f}")
                        st.caption(tax.get("note", ""))
                        if tax["tax"] > 0:
                            st.metric("Net P&L after tax", f"₹{tax['net_pnl']:,.0f}")

                    # AI explanation
                    if a.get("explanation"):
                        st.info(f"💡 {a['explanation']}")

                    # Transaction history
                    with st.expander(f"Transaction history ({len(a['transactions'])} entries)"):
                        txn_df = pd.DataFrame(a["transactions"])
                        if not txn_df.empty:
                            st.dataframe(txn_df, hide_index=True, use_container_width=True)
                        if st.button(f"🗑 Remove all {a['fund_name']} holding data",
                                      key=f"del_hold_{a['amfi_code']}"):
                            remove_holding(a["amfi_code"])
                            st.rerun()


with tab4:
    result = _run_health()
    if "error" in result:
        st.error(result["error"])
        st.stop()

    df     = result["df"]
    nav_df = result["nav_df"]

    # ── NAV chart ─────────────────────────────────────────────────────────────
    st.subheader("📈 NAV History")
    selected_funds = st.multiselect(
        "Select funds to compare",
        options=df["Fund Name"].tolist(),
        default=df["Fund Name"].tolist()[:2],
    )
    if selected_funds:
        codes    = df[df["Fund Name"].isin(selected_funds)]["AMFI Code"].tolist()
        plot_nav = nav_df[nav_df["amfi_code"].isin(codes)].copy()

        # Normalise to 100 at start for apples-to-apples comparison
        def normalise(grp):
            grp = grp.sort_values("date")
            grp["norm_nav"] = grp["nav"] / grp["nav"].iloc[0] * 100
            return grp

        code_name = dict(zip(df["AMFI Code"], df["Fund Name"]))
        plot_nav["fund_label"] = plot_nav["amfi_code"].map(code_name)
        plot_nav = plot_nav.groupby("amfi_code", group_keys=False).apply(normalise)

        fig = px.line(plot_nav, x="date", y="norm_nav", color="fund_label",
                      labels={"norm_nav": "Normalised NAV (base=100)", "date": "", "fund_label": "Fund"},
                      height=400)
        fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ── Risk-return scatter ───────────────────────────────────────────────────
    st.subheader("📊 Risk vs Return (3Y)")
    scatter_df = df.dropna(subset=["3Y Return", "Volatility"])
    if not scatter_df.empty:
        fig2 = px.scatter(
            scatter_df,
            x="Volatility", y="3Y Return",
            color="Status",
            size="Score",
            hover_name="Fund Name",
            color_discrete_map={"HEALTHY": "#22863a", "WATCH": "#b08800", "REVIEW": "#c0392b"},
            labels={"Volatility": "Volatility (%)", "3Y Return": "3Y CAGR (%)"},
            height=400,
        )
        fig2.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig2, use_container_width=True)

    st.divider()

    # ── Full metrics table ────────────────────────────────────────────────────
    st.subheader("📋 Full Metrics Table")
    display_cols = ["Fund Name", "Category", "1Y Return", "3Y Return", "5Y Return",
                    "Sharpe", "Sortino", "Volatility", "Max Drawdown", "Alpha", "Beta",
                    "Consistency", "Score", "Status"]
    st.dataframe(
        df[display_cols].style.applymap(
            lambda v: "color: #22863a; font-weight: bold" if v == "HEALTHY"
                      else ("color: #b08800; font-weight: bold" if v == "WATCH"
                            else ("color: #c0392b; font-weight: bold" if v == "REVIEW" else "")),
            subset=["Status"]
        ),
        use_container_width=True,
        hide_index=True,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 5 — FUND DISCOVERY
# ═══════════════════════════════════════════════════════════════════════════════
with tab5:
    st.subheader("🌐 Fund Discovery")
    st.info(
        "Enter any AMFI fund code to analyse an external fund against industry metrics. "
        "You can find AMFI codes at mfapi.in"
    )

    disc_col1, disc_col2 = st.columns([2, 1])
    with disc_col1:
        disc_code = st.text_input("Enter AMFI Code", placeholder="e.g. 120503")
    with disc_col2:
        disc_name = st.text_input("Fund Name (optional)", placeholder="e.g. SBI Bluechip")

    if st.button("🔍 Analyse Fund") and disc_code:
        with st.spinner("Fetching and analysing …"):
            from fetchers.nav_history_api import fetch_nav_history
            from analytics.returns        import compute_all_returns
            from analytics.risk           import compute_all_risk_metrics
            from scoring.health_score     import compute_total_score, get_fund_status, get_score_breakdown
            from repository.nav_repo      import load_nav
            from ai.explain               import generate_explanation

            disc_nav = fetch_nav_history(disc_code.strip())
            if disc_nav is None or disc_nav.empty:
                st.error("Could not fetch NAV data for this code.")
            else:
                from repository.nav_repo import save_nav
                save_nav(disc_nav)

                benchmark_df = load_nav([settings.nifty50_code])
                rets = compute_all_returns(disc_nav)
                if not rets.empty:
                    r = rets.iloc[0]
                    risk = compute_all_risk_metrics(disc_nav, benchmark_df)
                    score  = compute_total_score(r["return_1y"], r["return_3y"], r["return_5y"],
                                                 risk["sharpe"], risk["sortino"],
                                                 risk["max_drawdown"], risk["consistency"])
                    status = get_fund_status(score)
                    bd     = get_score_breakdown(r["return_1y"], r["return_3y"], r["return_5y"],
                                                 risk["sharpe"], risk["sortino"],
                                                 risk["max_drawdown"], risk["consistency"])

                    st.markdown(f"### {disc_name or disc_code} — Score {score}/100 — {status_badge(status)}")
                    c1, c2, c3, c4, c5, c6 = st.columns(6)
                    c1.metric("1Y CAGR",     _fmt_pct(r["return_1y"]))
                    c2.metric("3Y CAGR",     _fmt_pct(r["return_3y"]))
                    c3.metric("5Y CAGR",     _fmt_pct(r["return_5y"]))
                    c4.metric("Sharpe",      _fmt_num(risk["sharpe"]))
                    c5.metric("Volatility",  _fmt_pct(risk["volatility"]))
                    c6.metric("Max Drawdown",_fmt_pct(risk["max_drawdown"]))

                    metrics_for_ai = {**dict(r), **risk, "score": score, "status": status}
                    expl = generate_explanation(disc_code, disc_name or disc_code, metrics_for_ai)
                    st.info(f"💡 {expl}")

                    # NAV chart
                    disc_nav["norm_nav"] = disc_nav["nav"] / disc_nav["nav"].iloc[0] * 100
                    fig3 = px.line(disc_nav, x="date", y="norm_nav",
                                   labels={"norm_nav": "Normalised NAV (base=100)", "date": ""},
                                   height=300)
                    fig3.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
                    st.plotly_chart(fig3, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 6 — SETTINGS
# ═══════════════════════════════════════════════════════════════════════════════
with tab6:
    st.subheader("⚙️ Settings")

    # ── Risk profile ──────────────────────────────────────────────────────────
    st.markdown("#### Your Risk Profile")
    from repository.portfolio_repo import get_risk_profile, set_risk_profile
    current_profile = get_risk_profile()
    new_profile = st.selectbox(
        "Risk Appetite",
        ["conservative", "moderate", "aggressive"],
        index=["conservative", "moderate", "aggressive"].index(current_profile),
        help="Conservative: debt/large cap; Moderate: balanced; Aggressive: mid/small cap"
    )
    if st.button("💾 Save Risk Profile"):
        set_risk_profile(new_profile)
        st.success("Risk profile updated!")
        st.cache_data.clear()

    st.divider()

    # ── Manage portfolio ──────────────────────────────────────────────────────
    st.markdown("#### Manage Portfolio Funds")
    from repository.portfolio_repo import get_funds, add_fund, remove_fund

    funds = get_funds()
    if funds:
        for f in funds:
            c1, c2 = st.columns([5, 1])
            c1.markdown(f"**{f['fund_name']}** ({f['amfi_code']}) — {f['category']} — ₹{f['invested_amount']:,}")
            if c2.button("🗑️ Remove", key=f"rm_{f['amfi_code']}"):
                remove_fund(f["amfi_code"])
                st.success(f"Removed {f['fund_name']}")
                st.cache_data.clear()
                st.rerun()

    st.markdown("##### ➕ Add a New Fund")
    with st.form("add_fund_form"):
        af_name    = st.text_input("Fund Name")
        af_code    = st.text_input("AMFI Code")
        af_cat     = st.selectbox("Category", settings.fund_categories)
        af_invest  = st.number_input("Invested Amount (₹)", min_value=0, step=1000)
        af_sip     = st.number_input("Monthly SIP (₹, enter 0 if lump sum)", min_value=0, step=500)
        if st.form_submit_button("Add Fund"):
            if not af_name or not af_code:
                st.error("Fund Name and AMFI Code are required.")
            else:
                try:
                    add_fund({
                        "fund_name":       af_name,
                        "amfi_code":       af_code.strip(),
                        "category":        af_cat,
                        "invested_amount": af_invest,
                        "sip_amount":      af_sip,
                    })
                    st.success(f"Added {af_name}. Click Refresh to fetch its NAV data.")
                    st.cache_data.clear()
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))

    st.divider()

    # ── Data refresh ──────────────────────────────────────────────────────────
    st.markdown("#### NAV Data")
    nav_summary = _get_nav_summary()
    st.json(nav_summary)

    col_r1, col_r2 = st.columns(2)
    if col_r1.button("🔄 Refresh NAV Data (smart — skips fresh data)"):
        with st.spinner("Fetching latest NAV data …"):
            from services.data_refresh_service import refresh_portfolio_nav
            res = refresh_portfolio_nav(force=False)
        st.success(f"Done. Refreshed: {len(res['refreshed'])}  Failed: {len(res['failed'])}")
        st.cache_data.clear()
        st.rerun()

    if col_r2.button("⚡ Force Full Refresh (re-download all)"):
        with st.spinner("Force-fetching all NAV history …"):
            from services.data_refresh_service import refresh_portfolio_nav
            res = refresh_portfolio_nav(force=True)
        st.success(f"Done. Refreshed: {len(res['refreshed'])}  Failed: {len(res['failed'])}")
        st.cache_data.clear()
        st.rerun()



