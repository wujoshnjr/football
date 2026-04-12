import streamlit as st
import numpy as np
import requests
import datetime as dt
from zoneinfo import ZoneInfo
import pandas as pd

TAIPEI = ZoneInfo("Asia/Taipei")

SPORTS = [
    "soccer_epl",
    "soccer_spain_la_liga",
    "soccer_italy_serie_a",
    "soccer_germany_bundesliga",
    "soccer_france_ligue_one",
    "soccer_usa_mls"
]

# =========================
# TIME
# =========================
def now_taipei():
    return dt.datetime.now(TAIPEI)

def to_taipei(ts):
    try:
        t = pd.to_datetime(ts)
        if t.tzinfo is None:
            t = t.tz_localize("UTC")
        return t.tz_convert(TAIPEI)
    except:
        return None

# =========================
# SAFE FETCH (MULTI LEAGUE FIX)
# =========================
def fetch_all():

    key = st.secrets["API_KEYS"]["ODDS_API"]
    all_data = []

    for s in SPORTS:

        try:
            r = requests.get(
                f"https://api.the-odds-api.com/v4/sports/{s}/odds",
                params={
                    "api_key": key,
                    "regions": "eu",
                    "markets": "h2h",
                    "oddsFormat": "decimal"
                },
                timeout=10
            )

            if r.status_code == 200:
                data = r.json()

                if isinstance(data, list):
                    all_data.extend(data)

        except:
            continue

    return all_data

# =========================
# SAFE PARSER (NO DROP)
# =========================
def safe_odds(m):

    try:
        outs = m.get("bookmakers", [])

        if not outs:
            return None

        markets = outs[0].get("markets", [])

        if not markets:
            return None

        outcomes = markets[0].get("outcomes", [])

        if len(outcomes) < 3:
            return None

        return [o["price"] for o in outcomes]

    except:
        return None

# =========================
# SIGNAL ENGINE
# =========================
def signal_engine(odds):

    probs = np.array([1/o for o in odds])
    probs = probs / probs.sum()

    signal = (max(probs) - 0.33) * 3

    return probs, signal

# =========================
# APP
# =========================
st.title("🏦 v26 INSTITUTIONAL MULTI-MARKET SYSTEM (FIXED ZERO-DATA ISSUE)")

data = fetch_all()

shown = 0

for m in data:

    home = m.get("home_team")
    away = m.get("away_team")

    k = to_taipei(m.get("commence_time"))

    odds = safe_odds(m)

    st.markdown("━━━━━━━━━━━━━━━━━━")
    st.subheader(f"{away} vs {home}")

    if k:
        st.write(f"🕒 台北時間：{k.strftime('%Y-%m-%d %H:%M')}")
    else:
        st.write("🕒 台北時間：unknown")

    if not odds:
        st.warning("⚠️ No odds available → DISPLAY ONLY")
        continue

    probs, sig = signal_engine(odds)

    st.metric("Signal", round(sig, 4))

    st.write({
        "HOME": round(probs[0], 3),
        "DRAW": round(probs[1], 3),
        "AWAY": round(probs[2], 3),
    })

    shown += 1

st.success(f"Total matches shown: {shown}")
