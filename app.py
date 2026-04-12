import streamlit as st
import requests
import pandas as pd
import numpy as np
import datetime as dt
from zoneinfo import ZoneInfo

TAIPEI = ZoneInfo("Asia/Taipei")

# =========================
# CONFIG
# =========================
ODDS_LEAGUES = [
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
    n = now()
    return n <= t <= n + dt.timedelta(hours=24)

# =========================
# 1️⃣ ODDS API
# =========================
def get_odds():
    key = st.secrets["API_KEYS"].get("ODDS_API")

    url = "https://api.the-odds-api.com/v4/sports/soccer_epl/odds"

    r = requests.get(url, params={
        "api_key": key,
        "regions": "eu",
        "markets": "h2h"
    })

    if r.status_code == 401:
        st.error("❌ ODDS API QUOTA / KEY ERROR")
        return []

    if r.status_code != 200:
        st.error("❌ ODDS API FAIL")
        return []

    return r.json()

# =========================
# 2️⃣ SPORTMONKS (truth layer)
# =========================
def get_sportmonks():
    key = st.secrets["API_KEYS"].get("SPORTMONKS")

    if not key:
        return {}

    url = "https://api.sportmonks.com/v3/football/fixtures"

    r = requests.get(url, params={
        "api_token": key,
        "include": "participants;league"
    })

    if r.status_code != 200:
        return {}

    return r.json()

# =========================
# 3️⃣ NEWS API
# =========================
def get_news():
    key = st.secrets["API_KEYS"].get("NEWS_API")

    if not key:
        return {}

    url = "https://newsapi.org/v2/everything"

    r = requests.get(url, params={
        "q": "football",
        "apiKey": key
    })

    if r.status_code != 200:
        return {}

    return r.json()

# =========================
# MERGE ENGINE
# =========================
def merge_data(odds):
    matches = []

    for m in odds:

        if not m.get("bookmakers"):
            continue

        kickoff = to_taipei(m.get("commence_time"))
        if not kickoff:
            continue

        if not in_24h(kickoff):
            continue

        matches.append({
            "home": m["home_team"],
            "away": m["away_team"],
            "time": kickoff,
            "odds": m["bookmakers"][0]["markets"][0]["outcomes"]
        })

    return matches

# =========================
# MODEL
# =========================
def probs(odds):
    try:
        p = [1/o["price"] for o in odds]
        s = sum(p)
        return [x/s for x in p]
    except:
        return [0.33, 0.33, 0.34]

def pick(p):
    return ["HOME","DRAW","AWAY"][int(np.argmax(p))]

def score(pick):
    if pick == "HOME":
        return (2,1)
    if pick == "AWAY":
        return (1,2)
    return (1,1)

# =========================
# APP
# =========================
st.title("🏦 GLOBAL FOOTBALL QUANT SYSTEM vFINAL")

# LOAD DATA
odds = get_odds()
sportmonks = get_sportmonks()
news = get_news()

matches = merge_data(odds)

st.write("📊 MATCHES:", len(matches))

if len(matches) == 0:
    st.error("❌ NO MATCHES (API OR QUOTA ISSUE)")
    st.stop()

results = []

for m in matches:

    p = probs(m["odds"])
    pk = pick(p)

    results.append({
        "match": f"{m['away']} vs {m['home']}",
        "time": m["time"],
        "pick": pk,
        "score": score(pk),
        "prob": p
    })

# =========================
# OUTPUT
# =========================
for r in sorted(results, key=lambda x: x["time"]):

    st.markdown("---")
    st.write(f"⚽ {r['match']}")
    st.write(f"🕒 {r['time']}")
    st.write(f"🎯 PICK: {r['pick']}")
    st.write(f"⚽ SCORE: {r['score']}")
