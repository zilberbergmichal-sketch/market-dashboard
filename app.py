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
    page_title="Equity Equities & Crisis Radar Dashboard",
    page_icon="🕸️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Auto-refresh every 60 seconds
REFRESH_INTERVAL_SEC = 60
st_autorefresh(interval=REFRESH_INTERVAL_SEC * 1000, key="market_refresh_ticker")

# Equity-Only Default Assets
BASE_EQUITY_ASSETS = {
    "S&P 500": "^GSPC",
    "S&P 500 Synthetic (SPXS.L)": "SPXS.L",
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

# Fetch Long-Term Data (since 2000 for crisis-tested percentiles)
@st.cache_data(ttl=21600)
def fetch_equity_history(tickers_dict):
    data = {}
    start_date = "2000-01-01"
    
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

st.title("🕸️ Equity Radar & Percentile Dashboard")
st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} • Long-Term Distribution (Since 2000)")

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
    
    # 4. 1Y (Trailing 252 days)
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

for idx, (label, series) in enumerate(history_data.items()):
    m = get_metrics_and_percentiles(series)
    with cols[idx]:
        st.markdown(f"**{label}**")
        st.caption(f"{m['sample_years']:.1f}y history")
        st.markdown(f"### {m['current']:,.2f}")
        st.markdown(
            f"""
            <div style='font-size: 0.85rem; line-height: 1.5;'>
                <div>1D: {format_cell(m['daily'][0], m['daily'][1])}</div>
                <div>MTD: {format_cell(m['mtd'][0], m['mtd'][1])}</div>
                <div>YTD: {format_cell(m['ytd'][0], m['ytd'][1])}</div>
                <div>1Y: {format_cell(m['1y'][0], m['1y'][1])}</div>
            </div>
            """,
            unsafe_allow_html=True
        )

st.markdown("---")

# 3. Spider / Radar Chart Section
st.subheader("🕸️ Spider / Radar Chart Analysis")

radar_mode = st.radio(
    "Choose Radar Dimension:",
    ["Compare Assets across Horizons (1D, MTD, YTD, 1Y, Volatility)", "Compare Single Asset across Lookback Periods"],
    horizontal=True
)

if radar_mode == "Compare Assets across Horizons (1D, MTD, YTD, 1Y, Volatility)":
    radar_assets = st.multiselect(
        "Select assets to overlay on Radar:",
        options=list(history_data.keys()),
        default=list(history_data.keys())[:3]
    )
    
    categories = ["1D Percentile", "MTD Percentile", "YTD Percentile", "1Y Percentile", "Volatility Percentile"]
    
    fig_radar = go.Figure()
    for a in radar_assets:
        m = get_metrics_and_percentiles(history_data[a])
        values = [m["daily"][1], m["mtd"][1], m["ytd"][1], m["1y"][1], m["vol"][1]]
        values.append(values[0])  # Close radar loop
        
        fig_radar.add_trace(go.Scatterpolar(
            r=values,
            theta=categories + [categories[0]],
            fill='toself',
            name=a
        ))
        
    fig_radar.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 100], ticksuffix="%")
        ),
        showlegend=True,
        margin=dict(l=40, r=40, t=30, b=30)
    )
    st.plotly_chart(fig_radar, use_container_width=True)

else:
    # Single Asset Multi-Period Lookback Returns
    chosen_single = st.selectbox("Select Asset:", options=list(history_data.keys()))
    s = history_data[chosen_single]
    
    # Calculate returns for various periods
    today = s.index[-1]
    curr_val = s.iloc[-1]
    
    horizons = {
        "1W": 5,
        "1M": 21,
        "3M": 63,
        "6M": 126,
        "YTD": max(len(s[s.index >= pd.Timestamp(today.year, 1, 1)]) - 1, 1),
        "1Y": 252
    }
    
    radar_pctls = []
    labels = list(horizons.keys())
    for h_name, days in horizons.items():
        ret = ((curr_val - s.iloc[-min(days, len(s))]) / s.iloc[-min(days, len(s))]) * 100
        rolling_dist = s.pct_change(days).dropna() * 100
        pctl = percentileofscore(rolling_dist, ret, kind="weak")
        radar_pctls.append(pctl)
        
    radar_pctls.append(radar_pctls[0])
    
    fig_radar_single = go.Figure(go.Scatterpolar(
        r=radar_pctls,
        theta=labels + [labels[0]],
        fill='toself',
        name=chosen_single,
        line=dict(color="#1f77b4")
    ))
    fig_radar_single.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 100], ticksuffix="%")
        ),
        title=f"Percentile Footprint across Horizons - {chosen_single}",
        margin=dict(l=40, r=40, t=40, b=30)
    )
    st.plotly_chart(fig_radar_single,
