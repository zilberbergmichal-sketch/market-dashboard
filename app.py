import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date
from scipy.stats import percentileofscore
from streamlit_autorefresh import st_autorefresh

# 1. Page Configuration
st.set_page_config(
    page_title="Equity Radar & Historical Percentiles",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Auto-refresh every 60 seconds
REFRESH_INTERVAL_SEC = 60
st_autorefresh(interval=REFRESH_INTERVAL_SEC * 1000, key="market_refresh_ticker")

# Equity-Only Default Assets
BASE_EQUITY_ASSETS = {
    "S&P 500": "^GSPC",
    "Nasdaq 100": "^NDX",
    "TA-35": "TA35.TA",
    "MSCI World": "URTH"
}

st.sidebar.header("Equity Universe")
st.sidebar.caption(f"Auto-refresh: Every {REFRESH_INTERVAL_SEC}s")

# Allow removing and adding assets dynamically
all_available = list(BASE_EQUITY_ASSETS.keys())
selected_active = st.sidebar.multiselect(
    "Active Assets (Uncheck to remove):",
    options=all_available,
    default=all_available
)

new_ticker = st.sidebar.text_input("Add Equity Ticker (e.g. NVDA, AAPL, MSFT, IWM):").strip().upper()

# Build active dictionary
active_assets = {k: BASE_EQUITY_ASSETS[k] for k in selected_active}
if new_ticker:
    active_assets[new_ticker] = new_ticker

# Fetch Maximum Long-Term Data (Since 1950)
@st.cache_data(ttl=21600)
def fetch_equity_history(tickers_dict):
    data = {}
    start_date = "1950-01-01"
    
    for label, ticker in tickers_dict.items():
        try:
            df = yf.download(ticker, start=start_date, progress=False)
            if not df.empty:
                if isinstance(df.columns, pd.MultiIndex):
                    close_series = df["Close"][ticker]
                else:
                    close_series = df["Close"]
                
                close_series = close_series.dropna()
                if len(close_series) >= 252:
                    data[label] = close_series
        except Exception:
            continue
    return data

history_data = fetch_equity_history(active_assets)

st.title("🌐 Equity Radar & Historical Percentiles")
st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} • Maximum Historical Distribution (Up to 1950+)")

# Helper calculation function
def get_metrics_and_percentiles(series: pd.Series):
    current = series.iloc[-1]
    prev = series.iloc[-2]
    today = series.index[-1]
    sample_years = (series.index[-1] - series.index[0]).days / 365.25
    
    # 1. 1D
    daily_returns = series.pct_change().dropna() * 100
    daily_chg = daily_returns.iloc[-1]
    daily_pctl = percentileofscore(daily_returns, daily_chg, kind="weak")
    
    # 2. MTD
    month_start_data = series[series.index < pd.Timestamp(today.year, today.month, 1)]
    base_mtd = month_start_data.iloc[-1] if not month_start_data.empty else series.iloc[0]
    mtd_chg = ((current - base_mtd) / base_mtd) * 100
    monthly_rolling = series.pct_change(21).dropna() * 100
    mtd_pctl = percentileofscore(monthly_rolling, mtd_chg, kind="weak")
    
    # 3. YTD
    year_start_data = series[series.index < pd.Timestamp(today.year, 1, 1)]
    base_ytd = year_start_data.iloc[-1] if not year_start_data.empty else series.iloc[0]
    ytd_chg = ((current - base_ytd) / base_ytd) * 100
    trading_days_ytd = max(len(series[series.index >= pd.Timestamp(today.year, 1, 1)]) - 1, 1)
    ytd_rolling = series.pct_change(trading_days_ytd).dropna() * 100
    ytd_pctl = percentileofscore(ytd_rolling, ytd_chg, kind="weak")
    
    # 4. 1Y (Trailing 252 trading days)
    one_year_ago = series.iloc[-252] if len(series) >= 252 else series.iloc[0]
    one_year_chg = ((current - one_year_ago) / one_year_ago) * 100
    annual_rolling = series.pct_change(252).dropna() * 100
    one_year_pctl = percentileofscore(annual_rolling, one_year_chg, kind="weak")
    
    # 5. Volatility (Annualized 30-day realized volatility percentile)
    vol_series = series.pct_change().rolling(30).std() * np.sqrt(252) * 100
    current_vol = vol_series.iloc[-1]
    vol_pctl = percentileofscore(vol_series.dropna(), current_vol, kind="weak")

    return {
        "current": current,
        "sample_years": sample_years,
        "daily": (daily_chg, daily_pctl),
        "mtd": (mtd_chg, mtd_pctl),
        "ytd": (ytd_chg, ytd_pctl),
        "1y": (one_year_chg, one_year_pctl),
        "vol": (current_vol, vol_pctl)
    }

if not history_data:
    st.warning("No equity data loaded. Please verify active tickers in the sidebar.")
    st.stop()

# 2. Upper Metrics Section
st.subheader("Performance & Historical Percentiles")
cols = st.columns(len(history_data))

def format_cell(chg, pctl):
    color = "#09AB3B" if chg >= 0 else "#FF2B2B"
    return f"<span style='color:{color}; font-weight:600;'>{chg:+.2f}%</span> <span style='font-size:0.75rem; color:#888;'>({pctl:.0f}th pctl)</span>"

for idx, (label, series) in enumerate(history
