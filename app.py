import streamlit as st
import numpy as np
import requests
import datetime as dt
from zoneinfo import ZoneInfo
import pandas as pd

TAIPEI = ZoneInfo("Asia/Taipei")

# =========================
# TIME FILTER (24H ONLY)
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

def in_window(k):
    return now_taipei() <= k <= now_taipei() + dt.timedelta(hours=24)

# =========================
# APL-1 MARKET LAYER
# =========================
def fetch_odds():
    key = st.secrets["API_KEYS"]["ODDS_API"]

    r = requests.get(
        "https://api.the-odds-api.com/v4/sports/soccer_epl/odds",
        params={
            "api_key": key,
            "regions": "eu",
            "markets": "h2h",
            "oddsFormat": "decimal"
        }
    )

    if r.status_code != 200:
        return []

    return r.json()

# =========================
# APL-2 SPORTS INTELLIGENCE (SIMULATED HOOK)
# =========================
def lineup_risk():
    return np.random.uniform(-0.03, 0.03)

# =========================
# APL-3 HISTORICAL MODEL (WEAK WEIGHT)
# =========================
def historical_bias():
    return np.random.uniform(-0.02, 0.02)

# =========================
# MARKET SIGNAL ENGINE (MAIN DRIVER)
# =========================
def market_signal(odds):
    probs = [1/o for o in odds]
    s = sum(probs)
    probs = [p/s for p in probs]
    return max(probs) - np.mean(probs), probs

# =========================
# SHARP MONEY DETECTION
# =========================
def sharp_money(signal, odds):
    movement = max(odds) - min(odds)
    return movement > 0.4 and signal > 0.05

# =========================
# EXECUTION FILTER
# =========================
def should_execute(ev, signal):
    return ev > 0.03 and signal > 0.045

# =========================
# EV CALC
# =========================
def EV(p, odds):
    return (p * (odds - 1)) - (1 - p)

# =========================
# APP
# =========================
st.title("🏦 v25 PROFESSIONAL SPORTSBOOK HEDGE FUND")

data = fetch_odds()

matches = []
execs = []

for m in data:

    try:
        home = m["home_team"]
        away = m["away_team"]

        k = to_taipei(m["commence_time"])
        if not k or not in_window(k):
            continue

        outcomes = m["bookmakers"][0]["markets"][0]["outcomes"]
        odds = [o["price"] for o in outcomes]

        signal, probs = market_signal(odds)

        lineup = lineup_risk()
        hist = historical_bias()

        final_signal = signal + lineup + hist

        pick = ["HOME", "DRAW", "AWAY"][int(np.argmax(probs))]

        evs = {
            "HOME": EV(probs[0], odds[0]),
            "DRAW": EV(probs[1], odds[1]),
            "AWAY": EV(probs[2], odds[2])
        }

        ev = evs[pick]

        matches.append({
            "match": f"{away} vs {home}",
            "time": k,
            "signal": final_signal,
            "pick": pick,
            "ev": ev,
            "odds": odds,
            "sharp": sharp_money(final_signal, odds)
        })

        if should_execute(ev, final_signal):
            execs.append({
                "match": f"{away} vs {home}",
                "pick": pick,
                "ev": ev,
                "signal": final_signal
            })

    except:
        continue

# =========================
# DISPLAY
# =========================
st.subheader("🌍 ALL MATCHES (24H WINDOW)")

for m in sorted(matches, key=lambda x: x["time"]):

    st.markdown("━━━━━━━━━━━━━━━━━━")
    st.write(f"⚽ {m['match']}")
    st.write(f"🕒 {m['time'].strftime('%Y-%m-%d %H:%M')}")
    st.write(f"📡 Signal: {round(m['signal'],4)}")
    st.write(f"🎯 Pick: {m['pick']}")
    st.write(f"💰 EV: {round(m['ev'],3)}")

    if m["sharp"]:
        st.error("🚨 SHARP MONEY DETECTED")

# =========================
# EXECUTION SIGNALS
# =========================
st.subheader("💰 EXECUTION TRADES")

if not execs:
    st.info("No executable trades")

for e in execs:

    st.error("🚨 EXECUTE ORDER")
    st.write(f"⚽ {e['match']}")
    st.write(f"🎯 {e['pick']}")
    st.write(f"📡 Signal: {round(e['signal'],4)}")
    st.write(f"💰 EV: {round(e['ev'],3)}")
