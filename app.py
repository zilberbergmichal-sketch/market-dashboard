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
st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} • Percentile benchmarks dynamically calibrated to full available history per asset.")

# Helper calculation function
def get_metrics_and_percentiles(series: pd.Series):
    current = series.iloc[-1]
    prev = series.iloc[-2]
    today = series.index[-1]
    start_year = series.index[0].year
    start_date_str = series.index[0].strftime("%b %Y")
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
        "start_year": start_year,
        "start_date_str": start_date_str,
        "sample_years": sample_years,
        "total_days": len(series),
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
        st.markdown(f"<span style='color:#555; font-size:0.8rem;'>📅 Base: Since {m['start_date_str']} ({m['sample_years']:.1f}y)</span>", unsafe_allow_html=True)
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

# קיצורים תקניים ונקיים לצירים
categories = ["1D", "MTD", "YTD", "1Y", "Vol"]
asset_options = list(history_data.keys())

st.markdown("##### Individual Asset Footprints (Side-by-Side)")
col_radar1, col_radar2, col_radar3 = st.columns(3)

default_assets = asset_options[:3] if len(asset_options) >= 3 else asset_options
colors = ["#1f77b4", "#00cc96", "#ef553b"]

for i, (col, default_asset) in enumerate(zip([col_radar1, col_radar2, col_radar3], default_assets)):
    with col:
        chosen = st.selectbox(
            f"Select Asset {i+1}:",
            options=asset_options,
            index=asset_options.index(default_asset) if default_asset in asset_options else 0,
            key=f"radar_asset_{i}"
        )
        
        m = get_metrics_and_percentiles(history_data[chosen])
        st.caption(f"Base: **{m['sample_years']:.1f}y** (since {m['start_date_str']})")
        
        # ערכי האחוזונים
        pctls = [m["daily"][1], m["mtd"][1], m["ytd"][1], m["1y"][1], m["vol"][1]]
        pctls.append(pctls[0])  # סגירת המעגל
        
        # תוויות משולבות: אחוזון + הערך הנקוב בסוגריים
        labels = [
            f"{m['daily'][1]:.0f}%<br>({m['daily'][0]:+.1f}%)",
            f"{m['mtd'][1]:.0f}%<br>({m['mtd'][0]:+.1f}%)",
            f"{m['ytd'][1]:.0f}%<br>({m['ytd'][0]:+.1f}%)",
            f"{m['1y'][1]:.0f}%<br>({m['1y'][0]:+.1f}%)",
            f"{m['vol'][1]:.0f}%<br>({m['vol'][0]:.1f}%)"
        ]
        labels.append(labels[0])
        
        fig = go.Figure()
        fig.add_trace(go.Scatterpolar(
            r=pctls,
            theta=categories + [categories[0]],
            mode="lines+markers+text",
            line=dict(color=colors[i % len(colors)], width=3),
            marker=dict(size=6),
            text=labels,
            textposition="top right",
            hoverinfo="text",
            name=chosen
        ))
        
        fig.update_layout(
            polar=dict(
                radialaxis=dict(visible=True, range=[0, 100], ticksuffix="%", dtick=25)
            ),
            showlegend=False,
            title=dict(text=f"<b>{chosen}</b>", x=0.5, xanchor="center"),
            margin=dict(l=45, r=45, t=40, b=40),
            height=370
        )
        st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

# דיאגרמת עכביש רוחבית: הנכסים השונים על הצירים לפי תקופה נבחרת
st.markdown("##### Cross-Asset Horizon Radar (Assets on Axes)")
col_sel, _ = st.columns([2, 2])
with col_sel:
    selected_horizon = st.selectbox(
        "Choose Horizon to Compare Across Assets:",
        ["1D", "MTD", "YTD", "1Y", "Vol"]
    )

horizon_key_map = {
    "1D": "daily",
    "MTD": "mtd",
    "YTD": "ytd",
    "1Y": "1y",
    "Vol": "vol"
}

target_key = horizon_key_map[selected_horizon]

cross_assets = list(history_data.keys())
cross_pctls = []
cross_labels = []

for a in cross_assets:
    m = get_metrics_and_percentiles(history_data[a])
    val, pctl = m[target_key]
    cross_pctls.append(pctl)
    if selected_horizon == "Vol":
        cross_labels.append(f"{pctl:.0f}% ({val:.1f}%)")
    else:
        cross_labels.append(f"{pctl:.0f}% ({val:+.1f}%)")

cross_pctls.append(cross_pctls[0])
cross_labels.append(cross_labels[0])
cross_thetas = cross_assets + [cross_assets[0]]

fig_cross = go.Figure()
fig_cross.add_trace(go.Scatterpolar(
    r=cross_pctls,
    theta=cross_thetas,
    mode="lines+markers+text",
    line=dict(color="#636EFA", width=3),
    marker=dict(size=7),
    text=cross_labels,
    textposition="top center",
    name=selected_horizon
))

fig_cross.update_layout(
    polar=dict(
        radialaxis=dict(visible=True, range=[0, 100], ticksuffix="%", dtick=25)
    ),
    title=dict(text=f"<b>Relative Market Positioning — {selected_horizon} Percentiles & Values</b>", x=0.5, xanchor="center"),
    showlegend=False,
    margin=dict(l=50, r=50, t=50, b=40),
    height=450
)
st.plotly_chart(fig_cross, use_container_width=True)
