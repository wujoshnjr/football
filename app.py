import streamlit as st
import numpy as np
import requests
import datetime as dt
from zoneinfo import ZoneInfo
import pandas as pd

TAIPEI = ZoneInfo("Asia/Taipei")

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

def in_24h(k):
    now = now_taipei()
    return now <= k <= now + dt.timedelta(hours=24)

# =========================
# FETCH ALL MATCHES (NO OVER-FILTER)
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
# MARKET SIGNAL (PRIMARY DRIVER)
# =========================
def market_signal(odds):

    probs = [1/o for o in odds]
    s = sum(probs)
    probs = [p/s for p in probs]

    signal = max(probs) - np.mean(probs)

    return signal, probs

# =========================
# MODEL LAYER (SECONDARY)
# =========================
def model_bias():
    return np.random.uniform(-0.02, 0.02)

# =========================
# EXECUTION FILTER
# =========================
def should_execute(signal):
    return signal > 0.04

def stake(signal):
    return min(0.05, signal * 0.5)

# =========================
# APP
# =========================
st.title("🏦 v22 INSTITUTIONAL EXECUTION HEDGE FUND")

data = fetch_all()

all_matches = []
exec_signals = []

for m in data:

    try:
        home = m["home_team"]
        away = m["away_team"]

        k = to_taipei(m["commence_time"])

        if not k or not in_24h(k):
            continue

        outcomes = m["bookmakers"][0]["markets"][0]["outcomes"]
        odds = [o["price"] for o in outcomes]

        signal, probs = market_signal(odds)

        model_adj = model_bias()

        final_signal = signal + model_adj

        pick_idx = int(np.argmax(probs))
        pick = ["HOME", "DRAW", "AWAY"][pick_idx]

        match_data = {
            "match": f"{away} vs {home}",
            "time": k,
            "signal": final_signal,
            "pick": pick,
            "probs": probs
        }

        all_matches.append(match_data)

        if should_execute(final_signal):
            exec_signals.append({
                **match_data,
                "stake": stake(final_signal)
            })

    except:
        continue

# =========================
# STAGE A: ALL MATCHES
# =========================
st.subheader("📊 ALL MATCHES (24H WINDOW)")

for m in sorted(all_matches, key=lambda x: x["time"]):

    st.markdown("━━━━━━━━━━━━━━━━━━")
    st.write(f"⚽ {m['match']}")
    st.write(f"🕒 {m['time'].strftime('%Y-%m-%d %H:%M')}")
    st.write(f"📡 Signal: {round(m['signal'],4)}")
    st.write(f"🎯 Pick: {m['pick']}")
    st.write({
        "HOME": round(m["probs"][0],3),
        "DRAW": round(m["probs"][1],3),
        "AWAY": round(m["probs"][2],3),
    })

# =========================
# STAGE B: EXECUTION SIGNALS
# =========================
st.subheader("💰 EXECUTION SIGNALS")

if not exec_signals:
    st.info("No trade signals currently")

for e in sorted(exec_signals, key=lambda x: x["signal"], reverse=True):

    st.error("🚨 EXECUTE TRADE")
    st.write(f"⚽ {e['match']}")
    st.write(f"📡 Signal: {round(e['signal'],4)}")
    st.write(f"💰 Stake: {round(e['stake'],4)}")
    st.write(f"🎯 Pick: {e['pick']}")
