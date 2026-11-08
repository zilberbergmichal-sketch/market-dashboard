# 3. Spider / Radar Chart Section (Side-by-Side Clean Outlines)
st.subheader("🕸️ Spider / Radar Chart Analysis")

categories = ["1D Percentile", "MTD Percentile", "YTD Percentile", "1Y Percentile", "Volatility Percentile"]
asset_options = list(history_data.keys())

# פריסה של 3 עמודות עם גרף נפרד לכל נכס
st.markdown("##### Individual Asset Footprints (Side-by-Side)")
col_radar1, col_radar2, col_radar3 = st.columns(3)

# ברירות מחדל לשלושת הנכסים
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
        values.append(values[0])  # סגירת המעגל
        
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

# אפשרות בונוס: השוואה באותו גרף אך ללא מילוי (Lines Only)
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
