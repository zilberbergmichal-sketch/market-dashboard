import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
from datetime import datetime, date
from streamlit_autorefresh import st_autorefresh

# 1. Page Configuration
st.set_page_config(
    page_title="Global Markets & FX Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Auto-refresh every 60 seconds
refresh_interval_sec = 60
st_autorefresh(interval=refresh_interval_sec * 1000, key="market_refresh_ticker")

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

# Sidebar: Asset management & configuration
st.sidebar.header("Settings & Assets")
st.sidebar.caption(f"Auto-refresh active: Every {refresh_interval_sec}s")

# Dynamic asset management
custom_ticker_input = st.sidebar.text_input("Add Ticker (e.g. AAPL, BTC-USD, NVDA):").strip().upper()
active_assets = DEFAULT_ASSETS.copy()

if custom_ticker_input:
    active_assets[custom_ticker_input] = custom_ticker_input

# Fetch price history with caching
@st.cache_data(ttl=55)
def fetch_full_history(tickers_dict):
    data = {}
    current_year = datetime.now().year
    start_date = f"{current_year - 5}-01-01"
    
    for label, ticker in tickers_dict.items():
        try:
            df = yf.download(ticker, start=start_date, progress=False)
            if not df.empty:
                # Handle possible MultiIndex from yfinance
                if isinstance(df.columns, pd.MultiIndex):
                    close_series = df["Close"][ticker]
                else:
                    close_series = df["Close"]
                
                close_series = close_series.dropna()
                if len(close_series) >= 2:
                    data[label] = close_series
        except Exception:
            continue
    return data

history_data = fetch_full_history(active_assets)

# Header Section
st.title("🌐 Global Markets & FX Dashboard")
now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
st.caption(f"Last updated: {now_str} (Auto-sync enabled)")

# Helper calculation function
def calculate_metrics(series: pd.Series):
    current = series.iloc[-1]
    prev = series.iloc[-2]
    daily_chg = ((current - prev) / prev) * 100

    today = series.index[-1]
    # MTD
    month_start_data = series[series.index < pd.Timestamp(today.year, today.month, 1)]
    if not month_start_data.empty:
        base_mtd = month_start_data.iloc[-1]
        mtd_chg = ((current - base_mtd) / base_mtd) * 100
    else:
        mtd_chg = ((current - series.iloc[0]) / series.iloc[0]) * 100

    # YTD
    year_start_data = series[series.index < pd.Timestamp(today.year, 1, 1)]
    if not year_start_data.empty:
        base_ytd = year_start_data.iloc[-1]
        ytd_chg = ((current - base_ytd) / base_ytd) * 100
    else:
        ytd_chg = ((current - series.iloc[0]) / series.iloc[0]) * 100

    return current, daily_chg, mtd_chg, ytd_chg

# 2. Top Section: KPI Cards
st.subheader("Market Overview (Daily, MTD, YTD)")

cols = st.columns(len(history_data))
for idx, (label, series) in enumerate(history_data.items()):
    current, daily_chg, mtd_chg, ytd_chg = calculate_metrics(series)
    val_format = "{:,.4f}" if "ILS" in label else "{:,.2f}"
    
    with cols[idx]:
        st.markdown(f"**{label}**")
        st.markdown(f"### {val_format.format(current)}")
        
        c_day, c_mtd, c_ytd = ("#09AB3B" if daily_chg >= 0 else "#FF2B2B",
                               "#09AB3B" if mtd_chg >= 0 else "#FF2B2B",
                               "#09AB3B" if ytd_chg >= 0 else "#FF2B2B")
        
        st.markdown(
            f"""
            <div style='font-size: 0.85rem; line-height: 1.4;'>
                <div>1D: <span style='color:{c_day}; font-weight:600;'>{daily_chg:+.2f}%</span></div>
                <div>MTD: <span style='color:{c_mtd}; font-weight:600;'>{mtd_chg:+.2f}%</span></div>
                <div>YTD: <span style='color:{c_ytd}; font-weight:600;'>{ytd_chg:+.2f}%</span></div>
            </div>
            """, 
            unsafe_allow_html=True
        )

st.markdown("---")

# 3. Bottom Section: Comparative Chart & Indexing
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
        ["1 Month", "3 Months", "6 Months", "YTD", "1 Year", "3 Years", "5 Years", "Custom"]
    )

with col_ctrl3:
    normalize = st.toggle("Rebase / Normalize (Base 100)", value=True if len(selected_assets) > 1 else False)

# Handle Custom Dates
if time_preset == "Custom":
    date_col1, date_col2 = st.columns(2)
    with date_col1:
        start_date_filter = st.date_input("Start Date", value=date.today() - pd.Timedelta(days=180))
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
    else:
        start_date_filter = end_date_filter - pd.Timedelta(days=365 * 5)

if selected_assets:
    combined_df = pd.DataFrame()
    for asset in selected_assets:
        s = history_data[asset]
        s_filtered = s[(s.index.date >= start_date_filter) & (s.index.date <= end_date_filter)]
        if not s_filtered.empty:
            if normalize:
                # Rebase to 100
                first_val = s_filtered.iloc[0]
                combined_df[asset] = (s_filtered / first_val) * 100
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
        st.warning("No data found for the selected date range.")
else:
    st.info("Select at least one asset to display the chart.")
