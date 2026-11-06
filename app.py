import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
from streamlit_autorefresh import st_autorefresh

# הגדרות תצוגה כלליות (מותאם למובייל ומחשב)
st.set_page_config(page_title="Market Pulse", layout="wide", initial_sidebar_state="collapsed")

# רענון אוטומטי כל 60 שניות (60,000 מילי-שניות)
count = st_autorefresh(interval=60 * 1000, key="datarefresh")

st.title("📊 דשבורד שווקים ומט״ח")
st.caption(f"עדכון אוטומטי כל 60 שניות • ספירת רענונים: {count}")

# מפת הנכסים והטיקרים
ASSETS = {
    "S&P 500": "^GSPC",
    "Nasdaq 100": "^NDX",
    "ת״א 35": "TA35.TA",
    "MSCI World (URTH)": "URTH",
    "USD / ILS": "ILS=X",
    "EUR / ILS": "EURILS=X",
    "נפט גולמי (WTI)": "CL=F"
}

@st.cache_data(ttl=55)  # שמירה במטמון ל-55 שניות למניעת עומס קריאות
def get_market_data(tickers_dict):
    data = {}
    for name, ticker in tickers_dict.items():
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="5d", interval="1d")
            if len(hist) >= 2:
                current_price = hist['Close'].iloc[-1]
                prev_price = hist['Close'].iloc[-2]
                pct_change = ((current_price - prev_price) / prev_price) * 100
                data[name] = {
                    "price": current_price,
                    "change": pct_change,
                    "history": hist['Close']
                }
        except Exception:
            continue
    return data

data = get_market_data(ASSETS)

# תצוגת כרטיסי מחיר ושינוי יומי
st.subheader("שערים ושינוי יומי")
cols = st.columns(len(ASSETS))

for i, (name, info) in enumerate(data.items()):
    with cols[i % len(cols)]:
        # הצגת דיוק שונה למט"ח לעומת מדדים
        format_str = "{:,.4f}" if "ILS" in name else "{:,.2f}"
        st.metric(
            label=name,
            value=format_str.format(info["price"]),
            delta=f"{info['change']:+.2f}%"
        )

# גרף השוואתי היסטורי
st.divider()
selected_asset = st.selectbox("בחר נכס לצפייה בגרף היסטורי:", list(ASSETS.keys()))

if selected_asset in data:
    # משיכת היסטוריה רחבה יותר עבור הגרף
    hist_chart = yf.Ticker(ASSETS[selected_asset]).history(period="1mo")
    fig = px.line(
        hist_chart,
        x=hist_chart.index,
        y="Close",
        title=f"גרף חודשי - {selected_asset}",
        labels={"Close": "שער סגירה", "Date": "תאריך"}
    )
    fig.update_layout(margin=dict(l=20, r=20, t=40, b=20))
    st.plotly_chart(fig, use_container_width=True)
