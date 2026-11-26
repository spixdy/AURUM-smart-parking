"""Streamlit dashboard (deployable on Streamlit Community Cloud)."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from . import places
from .db import Database
from .model import SLOT_STEP, WINDOW, Forecaster
from .vision import bay_counts

IST = ZoneInfo("Asia/Kolkata")
GOLD, GOLD2, INK, MUTED, BG = "#c9a96a", "#e8d3a2", "#f1ead9", "#9a9080", "#0b0a09"
FONTS = (
    "https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@300;500"
    "&family=Jost:wght@300;400&display=swap"
)
CSS = """
<style>
@import url('__FONTS__');
html, body, [class*="css"] { font-family: 'Jost', sans-serif; font-weight: 300; }
h1, h2, h3 { font-family: 'Cormorant Garamond', serif !important; font-weight: 300 !important; letter-spacing: .02em; }
h1 { font-size: 3.4rem !important; color: #e8d3a2; }
[data-testid="stMetricValue"] { font-family: 'Cormorant Garamond', serif; font-size: 3rem; color: #e8d3a2; }
[data-testid="stMetricLabel"] { letter-spacing: .25em; text-transform: uppercase; font-size: .7rem; color: #c9a96a; }
section[data-testid="stSidebar"] { border-right: 1px solid rgba(201,169,106,.25); }
.stTabs [data-baseweb="tab"] { letter-spacing: .2em; text-transform: uppercase; font-size: .75rem; }
</style>
"""


@st.cache_resource(show_spinner="Loading model…")
def get_forecaster() -> Forecaster:
    return Forecaster.load()  # trains on first run if the saved model is missing


@st.cache_resource
def get_db() -> Database:
    return Database()


def _layout(fig: go.Figure, title: str = "") -> go.Figure:
    fig.update_layout(
        title=title, paper_bgcolor=BG, plot_bgcolor=BG, font={"color": MUTED, "family": "Jost"},
        margin={"l": 10, "r": 10, "t": 50, "b": 10}, legend={"orientation": "h"},
        xaxis={"gridcolor": "rgba(201,169,106,.12)"}, yaxis={"gridcolor": "rgba(201,169,106,.12)"},
    )
    return fig


def _slot_label(t: float) -> str:
    return f"{int(t):02d}:{'30' if t % 1 else '00'}"


def main() -> None:
    st.set_page_config(page_title="AURUM · Delhi Parking Forecast", page_icon="🅿️", layout="wide")
    st.markdown(CSS.replace('__FONTS__', FONTS), unsafe_allow_html=True)
    fc = get_forecaster()
    today = datetime.now(IST).date()

    st.title("AURUM")
    st.caption("DELHI · PARKING INTELLIGENCE")

    with st.sidebar:
        st.header("Forecast")
        place = st.selectbox(  # typing in this box filters the list (built-in search)
            "Destination (type to search)", places.PLACES, format_func=lambda p: f"{p.name} · {p.area}",
        )
        day: date = st.date_input("Date", today, min_value=today, max_value=today + timedelta(days=365))
        slots = [WINDOW[0] + i * SLOT_STEP for i in range(int((WINDOW[1] - WINDOW[0]) / SLOT_STEP) + 1)]
        t = st.select_slider("Time", slots, value=13.0, format_func=_slot_label)
        st.markdown("**Conditions**")
        cond = {
            "rain": st.checkbox("Rain"),
            "holiday": st.checkbox("Public holiday"),
            "peak_event": st.checkbox("Peak-event day"),
        }

    when = datetime.combine(day, datetime.min.time()).replace(hour=int(t), minute=int(t % 1 * 60))
    pred = fc.predict(place.id, when, **cond)
    curve = fc.curve(place.id, day, **cond)
    xs = [_slot_label(WINDOW[0] + i * SLOT_STEP) for i in range(len(curve))]

    tab_f, tab_w, tab_l, tab_m, tab_c, tab_i = st.tabs(["Forecast", "Week", "Live", "Map", "Camera", "Model"])

    with tab_f:
        a, b, c, d = st.columns(4)
        a.metric("Expected vehicles", f"{pred.vehicles:,}")
        b.metric("Occupancy", f"{pred.ratio:.0%}")
        c.metric("80% range", f"{pred.low:,} – {pred.high:,}")
        quiet = min((p for p, x in zip(curve, xs, strict=True) if x >= "09:00"), key=lambda p: p.ratio)
        d.metric("Quietest after 09:00", xs[curve.index(quiet)])
        st.markdown(f"**{pred.status}** · capacity ~{pred.capacity:,} bays (indicative)")
        fig = go.Figure()
        fig.add_scatter(x=xs, y=[p.high for p in curve], line={"width": 0}, showlegend=False, hoverinfo="skip")
        fig.add_scatter(x=xs, y=[p.low for p in curve], fill="tonexty", fillcolor="rgba(201,169,106,.15)",
                        line={"width": 0}, name="80% range", hoverinfo="skip")
        fig.add_scatter(x=xs, y=[p.vehicles for p in curve], line={"color": GOLD2, "width": 2.5}, name="Forecast")
        fig.add_vline(x=_slot_label(t), line_color=GOLD, line_dash="dot")
        fig.add_hline(y=place.capacity, line_color=MUTED, line_dash="dash", annotation_text="capacity")
        st.plotly_chart(_layout(fig, f"{place.name} · {day:%A %d %b %Y}"))

    with tab_w:
        z = fc.week_matrix(place.id, **cond) * 100
        fig = go.Figure(go.Heatmap(
            z=z, x=xs, y=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"], zmin=0, zmax=100,
            colorscale=[[0, "#13110e"], [0.5, "#7a6238"], [1, GOLD2]], colorbar={"title": "%"},
        ))
        st.plotly_chart(_layout(fig, "Weekly rhythm · % of capacity"))

    with tab_l:
        db = get_db()
        rows = db.readings(place.id, limit=600)
        if not rows:
            st.info(
                "No live readings yet. Start the pipeline (`docker compose up`) or load demo history "
                "with `python -m aurum.simulator --offline --backfill 3`."
            )
        else:
            df = pd.DataFrame({
                "time": [r.ts.astimezone(IST).replace(tzinfo=None) for r in rows],
                "actual": [r.occupied for r in rows],
                "forecast": [fc.predict(place.id, r.ts.astimezone(IST).replace(tzinfo=None)).vehicles for r in rows],
            })
            err = (df.actual - df.forecast).abs().mean()
            m1, m2, m3 = st.columns(3)
            m1.metric("Latest reading", f"{rows[-1].occupied:,}")
            m2.metric("Readings stored", f"{len(rows):,}")
            m3.metric("Mean abs. gap vs forecast", f"{err:,.0f} vehicles")
            fig = go.Figure()
            fig.add_scatter(x=df.time, y=df.actual, name="Actual (sensor)", line={"color": GOLD2})
            fig.add_scatter(x=df.time, y=df.forecast, name="Forecast", line={"color": MUTED, "dash": "dot"})
            st.plotly_chart(_layout(fig, "Live readings vs forecast"))
            latest = db.latest()
            st.dataframe(pd.DataFrame([
                {"place": places.BY_ID[k].name, "occupied": v.occupied, "capacity": v.capacity,
                 "pct": round(100 * v.occupied / v.capacity), "source": v.source,
                 "as of": v.ts.astimezone(IST).strftime("%d %b %H:%M")}
                for k, v in latest.items()
            ]), hide_index=True)

    with tab_m:
        ratios = {p.id: fc.predict(p.id, when, **cond).ratio for p in places.PLACES}
        df = pd.DataFrame([{"lat": p.lat, "lon": p.lon, "size": 80 + 400 * ratios[p.id]} for p in places.PLACES])
        st.map(df, latitude="lat", longitude="lon", size="size", color="#c9a96a")
        st.dataframe(pd.DataFrame([
            {"place": p.name, "area": p.area, "type": p.kind, "forecast %": round(100 * ratios[p.id])}
            for p in places.PLACES
        ]).sort_values("forecast %", ascending=False), hide_index=True)

    with tab_c:
        v = bay_counts()
        st.markdown("Annotated camera frames (CVAT): how full each frame's bays are.")
        c1, c2, c3 = st.columns(3)
        c1.metric("Frames", len(v))
        c2.metric("Bays labelled", f"{int(v.bays.sum()):,}")
        c3.metric("Mean occupancy", f"{v.occupancy.mean():.0%}")
        fig = go.Figure(go.Bar(x=v.image.str.replace("images/", ""), y=v.occupancy * 100, marker_color=GOLD))
        st.plotly_chart(_layout(fig, "Occupancy per camera frame (%)"))

    with tab_i:
        m = fc.metrics
        c1, c2, c3 = st.columns(3)
        c1.metric("Holdout R²", f"{m['holdout_r2']:.2f}")
        c2.metric("Holdout MAE", f"{m['holdout_mae'] * 100:.1f} pts")
        c3.metric("Training rows", f"{m['train_rows']:,}")
        st.write(f"Dwell-time multipliers from 10,000 sessions: {fc.mods}")
        st.warning(
            "The occupancy data comes from 30 car parks in Birmingham, UK. Delhi places borrow a similar "
            "lot's pattern and use indicative capacities. Replace with Delhi sensor data and retrain "
            "for production use. Forecasts cover 07:00–17:30 only."
        )


if __name__ == "__main__":
    main()
