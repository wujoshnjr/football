import streamlit as st
import requests
import pandas as pd
import numpy as np
import datetime as dt
from zoneinfo import ZoneInfo

TAIPEI = ZoneInfo("Asia/Taipei")

# =========================
# TIME
# =========================
def now():
    return dt.datetime.now(TAIPEI)

def to_taipei(ts):
    t = pd.to_datetime(ts)
    if t.tzinfo is None:
        t = t.tz_localize("UTC")
    return t.tz_convert(TAIPEI)

def in_24h(t):
    return now() <= t <= now() + dt.timedelta(hours=24)

# =========================
# FETCH ODDS
# =========================
def get_odds():
    key = st.secrets["API_KEYS"]["ODDS_API"]

    url = "https://api.the-odds-api.com/v4/sports/soccer_epl/odds"

    r = requests.get(url, params={
        "api_key": key,
        "regions": "eu",
        "markets": "h2h"
    })

    if r.status_code != 200:
        return []

    return r.json()

# =========================
# NORMALIZE
# =========================
def normalize(data):

    matches = []

    for m in data:

        home = m.get("home_team")
        away = m.get("away_team")
        time = m.get("commence_time")

        if not home or not away:
            continue

        kickoff = to_taipei(time)

        if not in_24h(kickoff):
            continue

        try:
            outcomes = m["bookmakers"][0]["markets"][0]["outcomes"]
            odds = [o["price"] for o in outcomes]
        except:
            continue

        matches.append({
            "home": home,
            "away": away,
            "time": kickoff,
            "odds": odds
        })

    return matches

# =========================
# MARKET PROB
# =========================
def market_prob(odds):
    inv = [1/o for o in odds]
    s = sum(inv)
    return [x/s for x in inv]

# =========================
# MODEL ADJUSTMENTS
# =========================
def model_adjust(mp):

    # 不過度相信市場
    noise = np.random.normal(0, 0.05, 3)

    # 爆冷因子
    upset = np.random.uniform(-0.1, 0.1)

    p = [
        mp[0] + noise[0] + upset,
        mp[1] + noise[1],
        mp[2] + noise[2] - upset
    ]

    p = np.clip(p, 0.01, 0.98)
    s = sum(p)
    return [x/s for x in p]

# =========================
# MONTE CARLO 100000
# =========================
def simulate(probs, n=100000):

    outcomes = np.random.choice([0,1,2], size=n, p=probs)

    counts = np.bincount(outcomes, minlength=3)

    return counts / n

# =========================
# EV
# =========================
def ev(prob, odds):
    return prob * odds - 1

# =========================
# TRAP DETECTION（關鍵）
# =========================
def trap_flag(model_p, market_p):

    diff_home = model_p[0] - market_p[0]
    diff_away = model_p[2] - market_p[2]

    # 市場明顯偏一邊但模型不支持
    if market_p[0] > 0.6 and model_p[0] < 0.5:
        return "⚠️ HOME TRAP"

    if market_p[2] > 0.6 and model_p[2] < 0.5:
        return "⚠️ AWAY TRAP"

    # 偏差過大
    if abs(diff_home) > 0.15 or abs(diff_away) > 0.15:
        return "⚠️ SUSPICIOUS"

    return "OK"

# =========================
# APP
# =========================
st.title("🏦 QUANT HEDGE FUND ENGINE v2")

data = get_odds()

matches = normalize(data)

if not matches:
    st.error("❌ NO MATCHES (CHECK API)")
    st.stop()

# 排序（台北時間最近在上）
matches = sorted(matches, key=lambda x: x["time"])

for m in matches:

    mp = market_prob(m["odds"])

    adj = model_adjust(mp)

    sim = simulate(adj)

    evs = [
        ev(sim[0], m["odds"][0]),
        ev(sim[1], m["odds"][1]),
        ev(sim[2], m["odds"][2])
    ]

    pick_idx = int(np.argmax(evs))
    pick = ["HOME", "DRAW", "AWAY"][pick_idx]

    trap = trap_flag(sim, mp)

    st.markdown("----")

    st.markdown(f"### ⚽ {m['away']} vs {m['home']}")

    st.write(f"🕒 Taipei Time: {m['time']}")

    st.write("📊 Market Prob:", [round(x,3) for x in mp])
    st.write("🤖 Model Prob:", [round(x,3) for x in sim])

    st.write("💰 EV:", [round(x,3) for x in evs])

    st.write(f"🎯 PICK: {pick}")

    st.write(f"🚨 Trap Analysis: {trap}")
