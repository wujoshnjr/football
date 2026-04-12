import streamlit as st
import numpy as np
import requests
import datetime as dt
from zoneinfo import ZoneInfo
import pandas as pd
import hashlib

TAIPEI = ZoneInfo("Asia/Taipei")

# =========================
# TIME WINDOW (KEY FIX)
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

def in_24h_window(kickoff):
    now = now_taipei()
    return now <= kickoff <= now + dt.timedelta(hours=24)

# =========================
# FETCH MARKET DATA
# =========================
def fetch_all():
    key = st.secrets["API_KEYS"]["ODDS_API"]
    url = "https://api.the-odds-api.com/v4/sports/soccer_epl/odds"

    r = requests.get(url, params={
        "api_key": key,
        "regions": "eu",
        "markets": "h2h",
        "oddsFormat": "decimal"
    })

    if r.status_code != 200:
        return []

    return r.json()

# =========================
# MARKET SIGNAL ENGINE (CORE)
# =========================
def market_signal(odds):

    # implied probabilities
    probs = [1/o for o in odds]
    total = sum(probs)
    probs = [p/total for p in probs]

    # signal strength = imbalance
    signal = max(probs) - np.mean(probs)

    return signal, probs

# =========================
# LINEUP / NEWS ENGINE (SIMPLIFIED)
# =========================
def lineup_signal():
    # placeholder for real API (Opta / Sportmonks)
    return np.random.uniform(-0.05, 0.05)

# =========================
# RISK FILTER
# =========================
def risk_filter(signal):
    return signal > 0.05

# =========================
# MAIN APP
# =========================
st.title("🏦 v21 MARKET-FIRST QUANT SYSTEM (PRODUCTION DESIGN)")

data = fetch_all()

for m in data:

    try:
        home = m["home_team"]
        away = m["away_team"]

        kickoff = to_taipei(m["commence_time"])

        # ❗ ONLY 24H WINDOW
        if not kickoff or not in_24h_window(kickoff):
            continue

        books = m.get("bookmakers", [])
        if not books:
            continue

        outcomes = books[0]["markets"][0]["outcomes"]
        odds = [o["price"] for o in outcomes]

        signal, probs = market_signal(odds)

        lineup_adj = lineup_signal()

        final_signal = signal + lineup_adj

        if not risk_filter(final_signal):
            continue

        # MARKET DOMINANT DECISION
        pick_idx = int(np.argmax(probs))
        picks = ["HOME", "DRAW", "AWAY"]
        pick = picks[pick_idx]

        st.markdown("━━━━━━━━━━━━━━━━━━")
        st.subheader(f"{away} vs {home}")

        st.write(f"🕒 台北時間：{kickoff.strftime('%Y-%m-%d %H:%M')}")

        st.metric("MARKET SIGNAL", round(final_signal, 4))
        st.metric("PICK (market-driven)", pick)

        st.write("📊 IMPLIED PROBABILITIES")
        st.write({
            "HOME": round(probs[0], 3),
            "DRAW": round(probs[1], 3),
            "AWAY": round(probs[2], 3),
        })

        st.info("🧠 Model only used as confirmation layer (NOT driver)")

    except:
        continue
