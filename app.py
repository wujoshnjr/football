import streamlit as st
import requests
import pandas as pd
import numpy as np
import datetime as dt
from zoneinfo import ZoneInfo
from math import exp, factorial

TAIPEI = ZoneInfo("Asia/Taipei")

# =========================
# CONFIG
# =========================
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
def now():
    return dt.datetime.now(TAIPEI)

def to_taipei(ts):
    try:
        t = pd.to_datetime(ts)
        if t.tzinfo is None:
            t = t.tz_localize("UTC")
        return t.tz_convert(TAIPEI)
    except:
        return None

def in_24h(t):
    return now() <= t <= now() + dt.timedelta(hours=24)

# =========================
# ODDS API
# =========================
def fetch_odds():
    key = st.secrets["API_KEYS"]["ODDS_API"]

    all_data = []

    for s in SPORTS:
        url = f"https://api.the-odds-api.com/v4/sports/{s}/odds"

        r = requests.get(url, params={
            "api_key": key,
            "regions": "eu",
            "markets": "h2h"
        })

        if r.status_code == 200:
            try:
                all_data += r.json()
            except:
                continue

    return all_data

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
        if not kickoff or not in_24h(kickoff):
            continue

        try:
            odds = m["bookmakers"][0]["markets"][0]["outcomes"]
            odds = [o["price"] for o in odds]
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
    inv = [1/x for x in odds]
    s = sum(inv)
    return [x/s for x in inv]

# =========================
# 🧠 REAL FOOTBALL MODEL (Poisson)
# =========================
def estimate_lambda(mp):

    # 基準進球（簡化 xG proxy）
    base_goal = 1.35

    home_adv = 0.15

    lam_home = base_goal * (mp[0] + home_adv)
    lam_away = base_goal * (mp[2])

    return max(lam_home,0.2), max(lam_away,0.2)

# =========================
# POISSON SIMULATION (100K)
# =========================
def poisson_sim(lh, la, n=100000):

    max_goals = 6

    results = {}

    for _ in range(n):

        hg = np.random.poisson(lh)
        ag = np.random.poisson(la)

        key = f"{hg}-{ag}"
        results[key] = results.get(key, 0) + 1

    sorted_scores = sorted(results.items(), key=lambda x: x[1], reverse=True)

    return sorted_scores[:5]

# =========================
# EV
# =========================
def ev(prob, odds):
    return prob * odds - 1

# =========================
# TRAP DETECTION
# =========================
def trap(market, model):

    if market[0] > 0.65 and model[0] < 0.55:
        return "⚠️ HOME TRAP"

    if market[2] > 0.65 and model[2] < 0.55:
        return "⚠️ AWAY TRAP"

    return "OK"

# =========================
# PROB FROM POISSON SIM
# =========================
def result_prob(scores):

    home_w = draw = away_w = 0

    total = sum([x[1] for x in scores])

    for s, c in scores:
        h, a = map(int, s.split("-"))

        if h > a:
            home_w += c
        elif h == a:
            draw += c
        else:
            away_w += c

    return [home_w/total, draw/total, away_w/total]

# =========================
# APP
# =========================
st.title("🏦 QUANT HEDGE FUND V4 (REAL SCORE AI)")

raw = fetch_odds()

matches = normalize(raw)

if not matches:
    st.warning("⚠️ fallback mode")
    matches = [
        {"home":"A","away":"B","time":now(),"odds":[2.1,3.2,3.5]}
    ]

matches = sorted(matches, key=lambda x: x["time"])

for m in matches:

    mp = market_prob(m["odds"])

    lh, la = estimate_lambda(mp)

    top_scores = poisson_sim(lh, la, 100000)

    probs = result_prob(top_scores)

    pick = ["HOME","DRAW","AWAY"][int(np.argmax(probs))]

    st.markdown("---")

    st.markdown(f"### ⚽ {m['away']} vs {m['home']}")

    st.write("🕒 Taipei:", m["time"])

    st.write("📊 Market:", [round(x,3) for x in mp])

    st.write("⚽ Top 5 Scores:")
    for s in top_scores:
        st.write(s)

    st.write("📈 Prob:", [round(x,3) for x in probs])

    st.write("🎯 PICK:", pick)

    st.write("🚨 TRAP:", trap(mp, probs))
