import streamlit as st
import requests
import numpy as np
import pandas as pd
import datetime as dt
from zoneinfo import ZoneInfo

TAIPEI = ZoneInfo("Asia/Taipei")

# =========================
# GLOBAL MARKETS
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
# DATA SOURCES
# =========================
def odds_api():
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

def sportmonks():
    key = st.secrets["API_KEYS"]["SPORTMONKS"]
    url = "https://api.sportmonks.com/v3/football/fixtures"

    r = requests.get(url, params={
        "api_token": key,
        "include": "participants;league;statistics"
    })

    if r.status_code != 200:
        return {}

    return r.json()

def news():
    key = st.secrets["API_KEYS"]["NEWS_API"]

    r = requests.get("https://newsapi.org/v2/everything", params={
        "q": "football OR injury OR lineup",
        "apiKey": key
    })

    return r.json() if r.status_code == 200 else {}

# =========================
# NORMALIZE
# =========================
def normalize(data):

    out = []

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

        out.append({
            "home": home,
            "away": away,
            "time": kickoff,
            "odds": odds
        })

    return out

# =========================
# MARKET MODEL
# =========================
def market_prob(odds):
    inv = [1/x for x in odds]
    s = sum(inv)
    return [x/s for x in inv]

# =========================
# PLAYER + TEAM STRENGTH (simplified xG proxy)
# =========================
def strength_adjust(mp, news_data):

    injury_factor = 0.05 if news_data else 0.0

    home = mp[0] * (1 + injury_factor)
    draw = mp[1]
    away = mp[2] * (1 - injury_factor)

    s = home + draw + away
    return [home/s, draw/s, away/s]

# =========================
# POISSON MODEL (xG)
# =========================
def expected_goals(mp):

    base = 1.35

    home_xg = base * (mp[0] + 0.15)
    away_xg = base * (mp[2])

    return max(home_xg,0.2), max(away_xg,0.2)

# =========================
# MONTE CARLO 100K SCORE SIM
# =========================
def simulate_scores(lh, la, n=100000):

    results = {}

    for _ in range(n):
        hg = np.random.poisson(lh)
        ag = np.random.poisson(la)

        k = f"{hg}-{ag}"
        results[k] = results.get(k, 0) + 1

    sorted_scores = sorted(results.items(), key=lambda x: x[1], reverse=True)

    return sorted_scores[:5]

# =========================
# RESULT PROB
# =========================
def result_prob(scores):

    home = draw = away = 0
    total = sum([x[1] for x in scores])

    for s, c in scores:
        h, a = map(int, s.split("-"))

        if h > a:
            home += c
        elif h == a:
            draw += c
        else:
            away += c

    return [home/total, draw/total, away/total]

# =========================
# ASIAN HANDICAP (IMPORTANT NEW)
# =========================
def handicap_edge(prob, line=0):

    # simplified market interpretation
    if prob[0] > 0.55:
        return "HOME -0.5 value"
    elif prob[2] > 0.55:
        return "AWAY +0.5 value"
    else:
        return "NO CLEAR EDGE"

# =========================
# KELLY BETTING
# =========================
def kelly(prob, odds):

    edge = prob * odds - 1
    return max(0, edge / odds)

# =========================
# TRAP DETECTION
# =========================
def trap(market, model):

    if market[0] > 0.65 and model[0] < 0.55:
        return "⚠️ MARKET TRAP HOME"

    if market[2] > 0.65 and model[2] < 0.55:
        return "⚠️ MARKET TRAP AWAY"

    return "OK"

# =========================
# APP UI
# =========================
st.title("🏦 V5 INSTITUTIONAL HEDGE FUND ENGINE")

odds_raw = odds_api()
sm = sportmonks()
news = news()

matches = normalize(odds_raw)

if not matches:
    st.warning("⚠️ fallback mode")
    matches = [{
        "home":"A","away":"B","time":now(),"odds":[2.1,3.2,3.5]
    }]

matches = sorted(matches, key=lambda x: x["time"])

for m in matches:

    mp = market_prob(m["odds"])

    mp2 = strength_adjust(mp, news)

    lh, la = expected_goals(mp2)

    scores = simulate_scores(lh, la, 100000)

    prob = result_prob(scores)

    pick = ["HOME","DRAW","AWAY"][int(np.argmax(prob))]

    st.markdown("----")

    st.markdown(f"### ⚽ {m['away']} vs {m['home']}")

    st.write("🕒 Taipei:", m["time"])

    st.write("📊 Market Prob:", [round(x,3) for x in mp])

    st.write("🧠 Model Prob:", [round(x,3) for x in prob])

    st.write("⚽ Top Scores:", scores)

    st.write("📈 Pick:", pick)

    st.write("💰 Handicap:", handicap_edge(prob))

    st.write("🎯 Kelly:", [round(kelly(prob[i], m["odds"][i]),3) for i in range(3)])

    st.write("🚨 Trap:", trap(mp, prob))
