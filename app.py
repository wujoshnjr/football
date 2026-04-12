import streamlit as st
import numpy as np
import requests
import pandas as pd
import datetime as dt
from zoneinfo import ZoneInfo

TAIPEI = ZoneInfo("Asia/Taipei")

SPORTS = [
    "soccer_epl","soccer_spain_la_liga","soccer_italy_serie_a",
    "soccer_germany_bundesliga","soccer_france_ligue_one",
    "soccer_netherlands_eredivisie","soccer_usa_mls",
    "soccer_brazil_serie_a","soccer_japan_j_league"
]

def now():
    return dt.datetime.now(TAIPEI)

def convert(ts):
    t = pd.to_datetime(ts)
    if t.tzinfo is None:
        t = t.tz_localize("UTC")
    return t.tz_convert(TAIPEI)

def in_24h(t):
    n = now()
    return n <= t <= n + dt.timedelta(hours=24)

def fetch():
    key = st.secrets["API_KEYS"]["ODDS_API"]
    all_data = []

    for s in SPORTS:
        try:
            r = requests.get(
                f"https://api.the-odds-api.com/v4/sports/{s}/odds",
                params={"api_key":key,"regions":"eu","markets":"h2h","oddsFormat":"decimal"},
                timeout=10
            )

            if r.status_code == 200:
                for m in r.json():
                    m["league"] = s
                    all_data.append(m)

        except:
            continue

    return all_data

def market(odds):
    p = [1/x for x in odds]
    s = sum(p)
    p = [x/s for x in p]
    return p

def ev(p, odds):
    return (p * odds) - 1

st.title("🏦 v28 INSTITUTIONAL SPORTSBOOK SYSTEM")

data = fetch()

results = []

for m in data:

    try:
        home = m["home_team"]
        away = m["away_team"]

        t = convert(m["commence_time"])
        if not in_24h(t):
            continue

        odds = [o["price"] for o in m["bookmakers"][0]["markets"][0]["outcomes"]]

        probs = market(odds)

        pred_score = {
            "HOME": (2,1),
            "DRAW": (1,1),
            "AWAY": (1,2)
        }

        pick = ["HOME","DRAW","AWAY"][np.argmax(probs)]

        results.append({
            "match": f"{away} vs {home}",
            "time": t,
            "league": m["league"],
            "pick": pick,
            "score": pred_score[pick],
            "prob": probs
        })

    except:
        continue

st.subheader("🌍 GLOBAL MATCHES (24H TAIPEI)")

for r in sorted(results, key=lambda x: x["time"]):

    st.write("━━━━━━━━━━━━━━")
    st.write(r["match"])
    st.write(r["time"].strftime("%Y-%m-%d %H:%M"))
    st.write("Pick:", r["pick"])
    st.write("Score:", r["score"])
