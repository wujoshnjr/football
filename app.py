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
LEAGUES = [
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
# SAFE VALUE GETTER (🔥核心修復)
# =========================
def safe_get_match(m):

    return {
        "home": m.get("home_team") or m.get("home") or "UNKNOWN",
        "away": m.get("away_team") or m.get("away") or "UNKNOWN",
        "time": m.get("commence_time") or m.get("time"),
        "bookmakers": m.get("bookmakers", [])
    }

# =========================
# ODDS API
# =========================
def fetch_odds():
    key = st.secrets["API_KEYS"].get("ODDS_API")

    url = "https://api.the-odds-api.com/v4/sports/soccer_epl/odds"

    r = requests.get(url, params={
        "api_key": key,
        "regions": "eu",
        "markets": "h2h"
    })

    if r.status_code != 200:
        return []

    try:
        return r.json()
    except:
        return []

# =========================
# FALLBACK (SAFE)
# =========================
def fallback_data():
    return [{
        "home": "DEMO HOME",
        "away": "DEMO AWAY",
        "time": "2026-04-12T18:00:00Z",
        "bookmakers": [{
            "markets": [{
                "outcomes": [
                    {"price": 2.1},
                    {"price": 3.2},
                    {"price": 3.5}
                ]
            }]
        }]
    }]

# =========================
# MERGE ENGINE (FINAL FIXED)
# =========================
def merge_matches(data):

    matches = []

    for raw in data:

        m = safe_get_match(raw)

        if not m["home"] or not m["away"]:
            continue

        kickoff = to_taipei(m["time"])
        if not kickoff:
            continue

        if not in_24h(kickoff):
            continue

        try:
            odds = m["bookmakers"][0]["markets"][0]["outcomes"]
        except:
            continue

        matches.append({
            "home": m["home"],
            "away": m["away"],
            "time": kickoff,
            "odds": odds
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
    return ["HOME", "DRAW", "AWAY"][int(np.argmax(p))]

def score(p):
    if p == "HOME":
        return (2,1)
    if p == "AWAY":
        return (1,2)
    return (1,1)

# =========================
# APP
# =========================
st.title("🏦 FINAL GLOBAL FOOTBALL ENGINE (STABLE)")

odds_raw = fetch_odds()

# 🔥 CRITICAL: SAFE FALLBACK
if not odds_raw:
    st.warning("⚠️ ODDS API EMPTY → USING FALLBACK")
    odds_raw = fallback_data()

matches = merge_matches(odds_raw)

st.write("📊 MATCHES:", len(matches))

# 🔥 NO MORE SILENT FAIL
if len(matches) == 0:
    st.error("❌ NO MATCHES AFTER PROCESSING (check time filter or API)")
    st.stop()

# =========================
# OUTPUT
# =========================
for m in sorted(matches, key=lambda x: x["time"]):

    p = probs(m["odds"])
    pk = pick(p)

    st.markdown("---")
    st.write(f"⚽ {m['away']} vs {m['home']}")
    st.write(f"🕒 {m['time']}")
    st.write(f"🎯 PICK: {pk}")
    st.write(f"⚽ SCORE: {score(pk)}")
