import streamlit as st
import requests
import pandas as pd
import numpy as np
import datetime as dt
from zoneinfo import ZoneInfo

TAIPEI = ZoneInfo("Asia/Taipei")

# =========================
# GLOBAL LEAGUES
# =========================
LEAGUES = [
    "soccer_epl",
    "soccer_spain_la_liga",
    "soccer_italy_serie_a",
    "soccer_germany_bundesliga",
    "soccer_france_ligue_one",
    "soccer_netherlands_eredivisie",
    "soccer_portugal_primeira_liga",
    "soccer_turkey_super_lig",
    "soccer_usa_mls",
    "soccer_brazil_serie_a",
    "soccer_japan_j_league",
    "soccer_korea_k_league"
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
# FETCH ALL LEAGUES
# =========================
def fetch_all():
    key = st.secrets["API_KEYS"]["ODDS_API"]
    all_matches = []

    for lg in LEAGUES:

        try:
            url = f"https://api.the-odds-api.com/v4/sports/{lg}/odds"

            r = requests.get(url, params={
                "api_key": key,
                "regions": "eu,us,uk,au",
                "markets": "h2h",
                "oddsFormat": "decimal"
            })

            if r.status_code != 200:
                st.warning(f"{lg} API failed")
                continue

            data = r.json()

            if not data:
                continue

            for m in data:

                if not m.get("bookmakers"):
                    continue

                kickoff = to_taipei(m.get("commence_time"))
                if not kickoff:
                    continue

                if not in_24h(kickoff):
                    continue

                all_matches.append({
                    "home": m["home_team"],
                    "away": m["away_team"],
                    "time": kickoff,
                    "league": lg,
                    "odds": m["bookmakers"][0]["markets"][0]["outcomes"]
                })

        except:
            continue

    return all_matches

# =========================
# MARKET MODEL
# =========================
def probs(odds):
    p = [1/o["price"] for o in odds]
    s = sum(p)
    return [x/s for x in p]

def pick_label(p):
    return ["HOME","DRAW","AWAY"][int(np.argmax(p))]

def score_sim(pick):
    if pick == "HOME":
        return (2,1)
    if pick == "AWAY":
        return (1,2)
    return (1,1)

# =========================
# APP
# =========================
st.title("🏦 GLOBAL FOOTBALL QUANT ENGINE (FINAL)")

data = fetch_all()

if not data:
    st.error("❌ NO MATCHES → API LIMIT OR WRONG KEY OR EMPTY FEED")

results = []

for m in data:

    try:
        p = probs(m["odds"])
        pick = pick_label(p)
        score = score_sim(pick)

        results.append({
            "match": f"{m['away']} vs {m['home']}",
            "time": m["time"],
            "league": m["league"],
            "pick": pick,
            "score": score,
            "prob": p
        })

    except:
        continue

# =========================
# DISPLAY (SORTED TIME)
# =========================
for r in sorted(results, key=lambda x: x["time"]):

    st.markdown("━━━━━━━━━━━━━━━━━━")
    st.write(f"⚽ {r['match']}")
    st.write(f"🏆 {r['league']}")
    st.write(f"🕒 {r['time'].strftime('%Y-%m-%d %H:%M')}")
    st.write(f"🎯 Pick: {r['pick']}")
    st.write(f"⚽ Score: {r['score']}")
