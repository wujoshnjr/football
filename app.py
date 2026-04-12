import streamlit as st
import requests
import pandas as pd
import numpy as np
import datetime as dt
from zoneinfo import ZoneInfo

# =========================
# CONFIG
# =========================
TAIPEI = ZoneInfo("Asia/Taipei")

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
# TIME HANDLING
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
# API FETCH (SAFE VERSION)
# =========================
def fetch_all_matches():
    key = st.secrets["API_KEYS"].get("ODDS_API")

    if not key:
        st.error("❌ Missing ODDS API KEY")
        return []

    all_matches = []

    for lg in LEAGUES:

        try:
            url = f"https://api.the-odds-api.com/v4/sports/{lg}/odds"

            r = requests.get(url, params={
                "api_key": key,
                "regions": "eu",
                "markets": "h2h",
                "oddsFormat": "decimal"
            }, timeout=10)

            # 🔥 DEBUG: NEVER HIDE ERRORS
            if r.status_code != 200:
                st.warning(f"{lg} API failed: {r.status_code}")
                continue

            try:
                data = r.json()
            except:
                st.warning(f"{lg} JSON parse error")
                continue

            if not data:
                st.warning(f"{lg} empty response")
                continue

            for m in data:

                # 🔥 SAFE GUARD (IMPORTANT FIX)
                if not m.get("bookmakers"):
                    continue

                kickoff = to_taipei(m.get("commence_time"))
                if not kickoff:
                    continue

                if not in_24h(kickoff):
                    continue

                all_matches.append({
                    "home": m.get("home_team"),
                    "away": m.get("away_team"),
                    "time": kickoff,
                    "league": lg,
                    "odds": m["bookmakers"][0]["markets"][0]["outcomes"]
                })

        except Exception as e:
            st.warning(f"{lg} exception: {str(e)}")
            continue

    return all_matches

# =========================
# MARKET MODEL
# =========================
def calc_probs(odds):
    try:
        p = [1/o["price"] for o in odds]
        s = sum(p)
        return [x/s for x in p]
    except:
        return [0.33, 0.33, 0.34]

def pick(probs):
    return ["HOME","DRAW","AWAY"][int(np.argmax(probs))]

def score_map(pick):
    if pick == "HOME":
        return (2,1)
    if pick == "AWAY":
        return (1,2)
    return (1,1)

# =========================
# APP
# =========================
st.title("🏦 GLOBAL FOOTBALL QUANT ENGINE (FINAL PRODUCTION)")

matches = fetch_all_matches()

# 🚨 IMPORTANT DEBUG
st.write(f"📊 TOTAL MATCHES LOADED: {len(matches)}")

if len(matches) == 0:
    st.error("❌ NO MATCHES FOUND → API KEY / LIMIT / REGION ISSUE")
    st.stop()

results = []

for m in matches:

    try:
        probs = calc_probs(m["odds"])
        p = pick(probs)
        score = score_map(p)

        results.append({
            "match": f"{m['away']} vs {m['home']}",
            "time": m["time"],
            "league": m["league"],
            "pick": p,
            "score": score,
            "prob": probs
        })

    except Exception as e:
        st.warning(f"Processing error: {str(e)}")
        continue

# =========================
# OUTPUT (SORTED BY TIME)
# =========================
st.subheader("🌍 GLOBAL MATCHES (24H TAIPEI TIME)")

for r in sorted(results, key=lambda x: x["time"]):

    st.markdown("━━━━━━━━━━━━━━━━━━")
    st.write(f"⚽ {r['match']}")
    st.write(f"🏆 {r['league']}")
    st.write(f"🕒 {r['time'].strftime('%Y-%m-%d %H:%M')}")
    st.write(f"🎯 PICK: {r['pick']}")
    st.write(f"⚽ SCORE: {r['score']}")
