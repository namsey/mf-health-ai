# MF Health AI

AI-powered mutual fund health analyser for Indian retail investors.

## Architecture

```
UI (app.py — Streamlit)
  └── services/          ← orchestration layer
        ├── health_service.py         — runs full analysis pipeline
        └── data_refresh_service.py   — NAV data refresh
              ├── repository/         ← data access layer
              │     ├── portfolio_repo.py   (portfolio CRUD)
              │     └── nav_repo.py         (NAV read/write)
              ├── fetchers/           ← external API calls
              │     └── nav_history_api.py  (mfapi.in)
              ├── analytics/          ← computation engine
              │     ├── returns.py    (CAGR, XIRR)
              │     └── risk.py       (Sharpe, Sortino, Beta, Alpha)
              ├── scoring/            ← classification
              │     └── health_score.py     (0-100 weighted score)
              ├── recommender/        ← advice engine
              │     └── switch_advisor.py   (category-aware switch)
              └── ai/                 ← AI with caching
                    └── explain.py          (GPT-4o-mini + TTL cache)
```

## Metrics Computed

| Metric | Description |
|--------|-------------|
| CAGR 1Y/3Y/5Y | Compound Annual Growth Rate — more accurate than point-to-point % |
| Sharpe Ratio | (Return - Risk Free) / Volatility — risk-adjusted returns |
| Sortino Ratio | Like Sharpe but only penalises downside volatility |
| Beta | Sensitivity to Nifty 50 benchmark |
| Alpha (Jensen's) | Return above what Beta predicts |
| Max Drawdown | Worst peak-to-trough loss |
| Consistency | % of trading days with positive returns |

## Scoring (0–100)

| Factor | Weight |
|--------|--------|
| 5Y CAGR | 25 |
| 3Y CAGR | 20 |
| Sharpe Ratio | 20 |
| Max Drawdown | 15 |
| Sortino Ratio | 10 |
| Consistency | 10 |

- **HEALTHY** ≥ 65
- **WATCH** 45–64  
- **REVIEW** < 45

## Quick Start

```bash
# 1. Clone / unzip the project
# 2. Create virtual environment
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure API key
cp .env.example .env
# Edit .env and add your OpenAI key (optional — app works without it)

# 5. Run
streamlit run app.py
```

On first run:
1. Go to **Settings** tab
2. Add your mutual fund AMFI codes (find them at https://www.mfapi.in)
3. Click **Refresh NAV Data** to fetch historical data (~1–2 min)
4. Switch to **Portfolio Health** tab

## Legal Disclaimer

This tool provides analytical insights for informational purposes only.
It is **not** SEBI-registered investment advice. Always consult a
SEBI-registered investment advisor before making investment decisions.
