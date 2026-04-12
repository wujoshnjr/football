import streamlit as st
import requests
import numpy as np
import pandas as pd
import datetime as dt
from zoneinfo import ZoneInfo

TAIPEI = ZoneInfo("Asia/Taipei")

# =========================
# GLOBAL LEAGUES
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
    t = pd.to_datetime(ts)
    if t.tzinfo is None:
        t = t.tz_localize("UTC")
    return t.tz_convert(TAIPEI)

def in_24h(t):
    return now() <= t <= now() + dt.timedelta(hours=24)

# =========================
# ODDS FETCH
# =========================
def fetch_odds():
    key = st.secrets["API_KEYS"]["ODDS_API"]

    data = []

    for s in SPORTS:
        url = f"https://api.the-odds-api.com/v4/sports/{s}/odds"

        r = requests.get(url, params={
            "api_key": key,
            "regions": "eu",
            "markets": "h2h,spreads,totals"
        })

        if r.status_code == 200:
            try:
                data += r.json()
            except:
                pass

    return data

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
# MARKET MODEL
# =========================
def market_prob(odds):
    inv = [1/x for x in odds]
    s = sum(inv)
    return [x/s for x in inv]

# =========================
# UPSERT MODEL (爆冷核心)
# =========================
def upset_model(mp):

    # underdog boost / favorite suppression
    upset = np.random.uniform(-0.12, 0.12)

    return [
        mp[0] * (1 + upset),
        mp[1],
        mp[2] * (1 - upset)
    ]

# =========================
# GOAL MODEL (xG proxy)
# =========================
def expected_goals(mp):

    base = 1.35

    home_xg = base * (mp[0] + 0.15)
    away_xg = base * mp[2]

    return max(home_xg, 0.2), max(away_xg, 0.2)

# =========================
# MONTE CARLO 100K
# =========================
def simulate(lh, la, n=100000):

    res = {}

    for _ in range(n):

        hg = np.random.poisson(lh)
        ag = np.random.poisson(la)

        k = f"{hg}-{ag}"
        res[k] = res.get(k, 0) + 1

    return sorted(res.items(), key=lambda x: x[1], reverse=True)[:5]

# =========================
# RESULT PROB
# =========================
def result_prob(scores):

    h = d = a = 0
    total = sum([x[1] for x in scores])

    for s, c in scores:
        hg, ag = map(int, s.split("-"))

        if hg > ag:
            h += c
        elif hg == ag:
            d += c
        else:
            a += c

    return [h/total, d/total, a/total]

# =========================
# OVER / UNDER MODEL
# =========================
def over_under(scores):

    over = 0
    under = 0

    total = sum([x[1] for x in scores])

    for s, c in scores:
        h, a = map(int, s.split("-"))
        if h + a >= 3:
            over += c
        else:
            under += c

    return over/total, under/total

# =========================
# EV
# =========================
def ev(p, odds):
    return p * odds - 1

# =========================
# KELLY
# =========================
def kelly(p, odds):
    return max(0, (p*odds - 1) / odds)

# =========================
# TRAP DETECTION
# =========================
def trap(mp, model):

    if mp[0] > 0.65 and model[0] < 0.55:
        return "⚠️ HOME TRAP"

    if mp[2] > 0.65 and model[2] < 0.55:
        return "⚠️ AWAY TRAP"

    return "OK"

# =========================
# UI CARD (一場一格🔥)
# =========================
def render_card(m, mp, model, scores, prob, ou):

    st.markdown("----")

    st.markdown(f"""
    ## ⚽ {m['away']}  vs  {m['home']}
    🕒 Taipei Time: {m['time']}
    """)

    st.markdown("### 📊 MARKET vs MODEL")

    st.write("Market:", [round(x,3) for x in mp])
    st.write("Model :", [round(x,3) for x in model])

    st.markdown("### ⚽ TOP SCORELINES")
    for s in scores:
        st.write(s)

    st.markdown("### 📈 MATCH PROBABILITY")
    st.write(f"Home / Draw / Away: {list(map(lambda x: round(x,3), prob))}")

    st.markdown("### 🔥 OVER / UNDER")
    st.write(f"Over: {round(ou[0],3)} | Under: {round(ou[1],3)}")

    pick = ["HOME","DRAW","AWAY"][int(np.argmax(prob))]

    st.markdown(f"### 🎯 PICK: {pick}")

    st.write("💰 EV:", [round(ev(prob[i], m['odds'][i]),3) for i in range(3)])

    st.write("📉 KELLY:", [round(kelly(prob[i], m['odds'][i]),3) for i in range(3)])

    st.write("🚨 TRAP:", trap(mp, model))

# =========================
# APP
# =========================
st.title("🏦 V6 INSTITUTIONAL TRADING DESK (FULL GLOBAL)")

raw = fetch_odds()

matches = normalize(raw)

if not matches:
    st.warning("⚠️ fallback mode")
    matches = [{
        "home":"A","away":"B","time":now(),"odds":[2.1,3.2,3.5]
    }]

matches = sorted(matches, key=lambda x: x["time"])

for m in matches:

    mp = market_prob(m["odds"])
    mp = upset_model(mp)

    lh, la = expected_goals(mp)

    scores = simulate(lh, la, 100000)

    prob = result_prob(scores)

    ou = over_under(scores)

    render_card(m, mp, mp, scores, prob, ou)
