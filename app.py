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

# 3. Spider / Radar Chart Section (Side-by-Side Clean Outlines)
st.subheader("🕸️ Spider / Radar Chart Analysis")

categories = ["1D Percentile", "MTD Percentile", "YTD Percentile", "1Y Percentile", "Volatility Percentile"]
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
        values = [m["daily"][1], m["mtd"][1], m["ytd"][1], m["1y"][1], m["vol"][1]]
        values.append(values[0])
        
        fig = go.Figure()
        fig.add_trace(go.Scatterpolar(
            r=values,
            theta=categories + [categories[0]],
            mode="lines+markers+text",
            line=dict(color=colors[i % len(colors)], width=3),
            marker=dict(size=7),
            text=[f"{v:.0f}%" for v in values],
            textposition="top right",
            name=chosen
        ))
        
        fig.update_layout(
            polar=dict(
                radialaxis=dict(visible=True, range=[0, 100], ticksuffix="%", dtick=25)
            ),
            showlegend=False,
            title=dict(text=f"<b>{chosen}</b>", x=0.5, xanchor="center"),
            margin=dict(l=35, r=35, t=40, b=30),
            height=360
        )
        st.plotly_chart(fig, use_container_width=True)

with st.expander("Show Combined Overlay (Lines Only, No Fill)"):
    overlay_selected = st.multiselect(
        "Select Assets to Overlay:",
        options=asset_options,
        default=default_assets,
        key="overlay_radar"
    )
    if overlay_selected:
        fig_overlay = go.Figure()
        for idx, a in enumerate(overlay_selected):
            m = get_metrics_and_percentiles(history_data[a])
            vals = [m["daily"][1], m["mtd"][1], m["ytd"][1], m["1y"][1], m["vol"][1]]
            vals.append(vals[0])
            
            fig_overlay.add_trace(go.Scatterpolar(
                r=vals,
                theta=categories + [categories[0]],
                mode="lines+markers",
                line=dict(width=2.5),
                marker=dict(size=6),
                name=a
            ))
            
        fig_overlay.update_layout(
            polar=dict(
                radialaxis=dict(visible=True, range=[0, 100], ticksuffix="%", dtick=25)
            ),
            showlegend=True,
            margin=dict(l=40, r=40, t=30, b=30),
            height=500
        )
        st.plotly_chart(fig_overlay, use_container_width=True)

st.markdown("---")

# 4. Multi-Horizon Comparative Line Chart (Base 100)
st.subheader("Historical Performance Chart (Rebase 100)")
col1, col2 = st.columns([3, 1])

with col1:
    chart_assets = st.multiselect(
        "Assets for Line Chart:",
        options=list(history_data.keys()),
        default=list(history_data.keys())
    )

with col2:
    time_preset = st.selectbox(
        "Time Horizon:",
        ["1 Month", "3 Months", "6 Months", "YTD", "1 Year", "3 Years", "5 Years", "10 Years", "20 Years", "30 Years", "Max Available"]
    )

end_date = date.today()
if time_preset == "1 Month":
    start_date = end_date - pd.Timedelta(days=30)
elif time_preset == "3 Months":
    start_date = end_date - pd.Timedelta(days=90)
elif time_preset == "6 Months":
    start_date = end_date - pd.Timedelta(days=180)
elif time_preset == "YTD":
    start_date = date(end_date.year, 1, 1)
elif time_preset == "1 Year":
    start_date = end_date - pd.Timedelta(days=365)
elif time_preset == "3 Years":
    start_date = end_date - pd.Timedelta(days=365 * 3)
elif time_preset == "5 Years":
    start_date = end_date - pd.Timedelta(days=365 * 5)
elif time_preset == "10 Years":
    start_date = end_date - pd.Timedelta(days=365 * 10)
elif time_preset == "20 Years":
    start_date = end_date - pd.Timedelta(days=365 * 20)
elif time_preset == "30 Years":
    start_date = end_date - pd.Timedelta(days=365 * 30)
else:
    start_date = date(1950, 1, 1)

if chart_assets:
    df_chart = pd.DataFrame()
    for a in chart_assets:
        s = history_data[a]
        s_cut = s[(s.index.date >= start_date) & (s.index.date <= end_date)]
        if not s_cut.empty:
            df_chart[a] = (s_cut / s_cut.iloc[0]) * 100

    if not df_chart.empty:
        fig_line = px.line(
            df_chart,
            x=df_chart.index,
            y=df_chart.columns,
            labels={"value": "Index (Base=100)", "Date": "Date", "variable": "Asset"},
            template="plotly_white"
        )
        fig_line.update_layout(
            hovermode="x unified",
            margin=dict(l=20, r=20, t=20, b=20),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_line, use_container_width=True)
