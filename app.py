import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime, date
from scipy.stats import percentileofscore
from streamlit_autorefresh import st_autorefresh

# 1. Page Configuration
st.set_page_config(
    page_title="Global Markets & Crisis-Tested Percentile Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Auto-refresh every 60 seconds
REFRESH_INTERVAL_SEC = 60
st_autorefresh(interval=REFRESH_INTERVAL_SEC * 1000, key="market_refresh_ticker")

# Default Assets
DEFAULT_ASSETS = {
    "S&P 500": "^GSPC",
    "Nasdaq 100": "^NDX",
    "TA-35": "TA35.TA",
    "MSCI World": "URTH",
    "USD / ILS": "ILS=X",
    "EUR / ILS": "EURILS=X",
    "Crude Oil (WTI)": "CL=F"
}

st.sidebar.header("Settings & Assets")
st.sidebar.caption(f"Auto-refresh: Every {REFRESH_INTERVAL_SEC}s")

# Add dynamic ticker
custom_ticker = st.sidebar.text_input("Add Ticker (e.g. NVDA, AAPL, BTC-USD):").strip().upper()
active_assets = DEFAULT_ASSETS.copy()
if custom_ticker:
    active_assets[custom_ticker] = custom_ticker

# Fetch Long-Term History (Since 2000: covers Dot-Com, 2008 GFC, 2020 Covid, 2022 Rates)
@st.cache_data(ttl=21600)  # Cache for 6 hours to keep load fast
def fetch_full_history(tickers_dict):
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

history_data = fetch_full_history(active_assets)

st.title("🌐 Global Markets & Percentile Rank Dashboard")
st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} • Long-Term Benchmark: Since 2000 (Crisis-Tested Distribution)")

# Helper calculation function
def get_metrics_and_percentiles(series: pd.Series):
    current = series.iloc[-1]
    prev = series.iloc[-2]
    today = series.index[-1]
    sample_years = (series.index[-1] - series.index[0]).days / 365.25
    
    # 1. Daily return & percentile against all historical 1-day returns
    daily_returns = series.pct_change().dropna() * 100
    daily_chg = daily_returns.iloc[-1]
    daily_pctl = percentileofscore(daily_returns, daily_chg, kind="weak")
    
    # 2. MTD return & percentile against historical 21-day rolling returns
    month_start_data = series[series.index < pd.Timestamp(today.year, today.month, 1)]
    base_mtd = month_start_data.iloc[-1] if not month_start_data.empty else series.iloc[0]
    mtd_chg = ((current - base_mtd) / base_mtd) * 100
    
    monthly_rolling = series.pct_change(21).dropna() * 100
    mtd_pctl = percentileofscore(monthly_rolling, mtd_chg, kind="weak")
    
    # 3. YTD return & percentile against historical rolling periods of equal length
    year_start_data = series[series.index < pd.Timestamp(today.year, 1, 1)]
    base_ytd = year_start_data.iloc[-1] if not year_start_data.empty else series.iloc[0]
    ytd_chg = ((current - base_ytd) / base_ytd) * 100
    
    trading_days_ytd = max(len(series[series.index >= pd.Timestamp(today.year, 1, 1)]) - 1, 1)
    ytd_rolling = series.pct_change(trading_days_ytd).dropna() * 100
    ytd_pctl = percentileofscore(ytd_rolling, ytd_chg, kind="weak")
    
    # 4. 1-Year (Trailing 252 trading days) return & percentile against rolling 1Y
    one_year_ago_data = series.iloc[-252] if len(series) >= 252 else series.iloc[0]
    one_year_chg = ((current - one_year_ago_data) / one_year_ago_data) * 100
    
    annual_rolling = series.pct_change(252).dropna() * 100
    one_year_pctl = percentileofscore(annual_rolling, one_year_chg, kind="weak")
    
    return {
        "current": current,
        "sample_years": sample_years,
        "daily": (daily_chg, daily_pctl),
        "mtd": (mtd_chg, mtd_pctl),
        "ytd": (ytd_chg, ytd_pctl),
        "1y": (one_year_chg, one_year_pctl)
    }

# 2. Upper Metrics Section
st.subheader("Performance & Long-Term Percentiles")
cols = st.columns(len(history_data))

def format_cell(chg, pctl):
    color = "#09AB3B" if chg >= 0 else "#FF2B2B"
    return f"<span style='color:{color}; font-weight:600;'>{chg:+.2f}%</span> <span style='font-size:0.75rem; color:#888;'>({pctl:.0f}th pctl)</span>"

for idx, (label, series) in enumerate(history_data.items()):
    m = get_metrics_and_percentiles(series)
    val_format = "{:,.4f}" if "ILS" in label else "{:,.2f}"
    
    with cols[idx]:
        st.markdown(f"**{label}**")
        st.caption(f"{m['sample_years']:.1f}y history")
        st.markdown(f"### {val_format.format(m['current'])}")
        
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

# 3. Percentile Heatmap Matrix
st.subheader("Percentile Rank Matrix (Full Historical Distribution)")
matrix_rows = []
for label, series in history_data.items():
    m = get_metrics_and_percentiles(series)
    matrix_rows.append({
        "Asset": label,
        "History (Years)": f"{m['sample_years']:.1f}",
        "Current Price": f"{m['current']:,.2f}",
        "1D Change": f"{m['daily'][0]:+.2f}%",
        "1D Percentile": round(m['daily'][1], 1),
        "MTD Change": f"{m['mtd'][0]:+.2f}%",
        "MTD Percentile": round(m['mtd'][1], 1),
        "YTD Change": f"{m['ytd'][0]:+.2f}%",
        "YTD Percentile": round(m['ytd'][1], 1),
        "1Y Change": f"{m['1y'][0]:+.2f}%",
        "1Y Percentile": round(m['1y'][1], 1),
    })

df_matrix = pd.DataFrame(matrix_rows)
st.dataframe(
    df_matrix.style.background_gradient(
        subset=["1D Percentile", "MTD Percentile", "YTD Percentile", "1Y Percentile"],
        cmap="RdYlGn",
        vmin=0,
        vmax=100
    ),
    use_container_width=True
)

st.markdown("---")

# 4. Multi-Horizon Chart & Rebase
st.subheader("Historical Performance & Comparative Analysis")
col_ctrl1, col_ctrl2, col_ctrl3 = st.columns([2, 1, 1])

with col_ctrl1:
    selected_assets = st.multiselect(
        "Select Assets to Compare:",
        options=list(history_data.keys()),
        default=[list(history_data.keys())[0]] if history_data else []
    )

with col_ctrl2:
    time_preset = st.selectbox(
        "Time Horizon:",
        ["1 Month", "3 Months", "6 Months", "YTD", "1 Year", "3 Years", "5 Years", "10 Years", "20 Years", "All (Since 2000)", "Custom"]
    )

with col_ctrl3:
    normalize = st.toggle("Rebase / Normalize (Base 100)", value=True if len(selected_assets) > 1 else False)

# Handle Horizon Filtering
if time_preset == "Custom":
    date_col1, date_col2 = st.columns(2)
    with date_col1:
        start_date_filter = st.date_input("Start Date", value=date.today() - pd.Timedelta(days=365 * 5))
    with date_col2:
        end_date_filter = st.date_input("End Date", value=date.today())
else:
    end_date_filter = date.today()
    if time_preset == "1 Month":
        start_date_filter = end_date_filter - pd.Timedelta(days=30)
    elif time_preset == "3 Months":
        start_date_filter = end_date_filter - pd.Timedelta(days=90)
    elif time_preset == "6 Months":
        start_date_filter = end_date_filter - pd.Timedelta(days=180)
    elif time_preset == "YTD":
        start_date_filter = date(end_date_filter.year, 1, 1)
    elif time_preset == "1 Year":
        start_date_filter = end_date_filter - pd.Timedelta(days=365)
    elif time_preset == "3 Years":
        start_date_filter = end_date_filter - pd.Timedelta(days=365 * 3)
    elif time_preset == "5 Years":
        start_date_filter = end_date_filter - pd.Timedelta(days=365 * 5)
    elif time_preset == "10 Years":
        start_date_filter = end_date_filter - pd.Timedelta(days=365 * 10)
    elif time_preset == "20 Years":
        start_date_filter = end_date_filter - pd.Timedelta(days=365 * 20)
    else:
        start_date_filter = date(2000, 1, 1)

if selected_assets:
    combined_df = pd.DataFrame()
    for asset in selected_assets:
        s = history_data[asset]
        s_filtered = s[(s.index.date >= start_date_filter) & (s.index.date <= end_date_filter)]
        if not s_filtered.empty:
            if normalize:
                combined_df[asset] = (s_filtered / s_filtered.iloc[0]) * 100
            else:
                combined_df[asset] = s_filtered

    if not combined_df.empty:
        fig = px.line(
            combined_df,
            x=combined_df.index,
            y=combined_df.columns,
            labels={"value": "Normalized Index (Base=100)" if normalize else "Price", "Date": "Date", "variable": "Asset"},
            template="plotly_white"
        )
        fig.update_layout(
            hovermode="x unified",
            margin=dict(l=20, r=20, t=30, b=20),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("No overlapping data found for the selected date range.")
else:
    st.info("Select at least one asset to display the chart.")
