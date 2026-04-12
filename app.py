import streamlit as st
import numpy as np
import requests
import datetime as dt
from zoneinfo import ZoneInfo
import pandas as pd

TAIPEI = ZoneInfo("Asia/Taipei")

# =========================
# TIME FILTER
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

def in_24h(k):
    return now_taipei() <= k <= now_taipei() + dt.timedelta(hours=24)

# =========================
# DATA
# =========================
def fetch_all():
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
# MARKET REGIME ENGINE
# =========================
def regime(probs):

    vol = np.std(probs)

    if vol > 0.05:
        return "STEAMING", 1.3
    elif vol < 0.02:
        return "FLAT", 1.0
    else:
        return "NORMAL", 1.1

# =========================
# SIGNAL ENGINE (FIXED)
# =========================
def signal_engine(probs, multiplier):

    max_p = max(probs)

    base_signal = (max_p - 0.33) * 3

    return base_signal * multiplier

# =========================
# EXECUTION MATRIX
# =========================
def decision(signal):

    if signal > 0.45:
        return "STRONG BUY"
    elif signal > 0.25:
        return "BUY"
    elif signal > 0.10:
        return "WATCH"
    else:
        return "AVOID"

# =========================
# APP
# =========================
st.title("🏦 v24 INSTITUTIONAL EXECUTION SYSTEM (FINAL TRADING DESK)")

data = fetch_all()

for m in data:

    try:
        home = m["home_team"]
        away = m["away_team"]

        k = to_taipei(m["commence_time"])

        if not k or not in_24h(k):
            continue

        outs = m["bookmakers"][0]["markets"][0]["outcomes"]
        odds = [o["price"] for o in outs]

        probs = np.array([1/o for o in odds])
        probs = probs / probs.sum()

        reg, mult = regime(probs)

        signal = signal_engine(probs, mult)

        exec_level = decision(signal)

        st.markdown("━━━━━━━━━━━━━━━━━━")
        st.subheader(f"{away} vs {home}")

        st.write(f"🕒 台北時間：{k.strftime('%Y-%m-%d %H:%M')}")
        st.write(f"📡 Market Regime: {reg}")
        st.metric("Signal", round(signal, 4))
        st.write(f"🎯 Execution: {exec_level}")

        st.write({
            "HOME": round(probs[0], 3),
            "DRAW": round(probs[1], 3),
            "AWAY": round(probs[2], 3),
        })

    except:
        continue
