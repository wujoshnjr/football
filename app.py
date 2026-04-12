import streamlit as st
import requests
import datetime as dt
from zoneinfo import ZoneInfo
import pandas as pd

TAIPEI = ZoneInfo("Asia/Taipei")

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
def to_taipei(ts):
    try:
        t = pd.to_datetime(ts)
        if t.tzinfo is None:
            t = t.tz_localize("UTC")
        return t.tz_convert(TAIPEI)
    except:
        return None

def in_24h(t):
    now = dt.datetime.now(TAIPEI)
    return now <= t <= now + dt.timedelta(hours=24)

# =========================
# API TEST (CRITICAL FIX)
# =========================
def test_api_key(key):
    url = "https://api.the-odds-api.com/v4/sports/soccer_epl/odds"

    r = requests.get(url, params={
        "api_key": key,
        "regions": "eu",
        "markets": "h2h",
        "oddsFormat": "decimal"
    })

    return r.status_code, r.text[:200]

# =========================
# FETCH
# =========================
def fetch_all():
    key = st.secrets["API_KEYS"].get("ODDS_API")

    if not key:
        st.error("❌ API KEY missing")
        return []

    # 🔥 DEBUG KEY STATUS
    status, text = test_api_key(key)
    st.write("🔑 API TEST STATUS:", status)
    st.write(text)

    if status == 401:
        st.error("❌ API KEY INVALID (401) → fix key first")
        return []

    all_matches = []

    for s in SPORTS:

        url = f"https://api.the-odds-api.com/v4/sports/{s}/odds"

        r = requests.get(url, params={
            "api_key": key,
            "regions": "eu",
            "markets": "h2h",
            "oddsFormat": "decimal"
        })

        # 🔥 SHOW ERROR INSTEAD OF SILENT FAIL
        if r.status_code != 200:
            st.warning(f"{s} failed: {r.status_code}")
            continue

        data = r.json()

        if not data:
            st.warning(f"{s} empty")
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
                "league": s
            })

    return all_matches

# =========================
# APP
# =========================
st.title("🚑 FIXED GLOBAL FOOTBALL ENGINE (DEBUG VERSION)")

matches = fetch_all()

st.write("📊 TOTAL MATCHES:", len(matches))

if not matches:
    st.error("❌ NO MATCHES → API KEY OR PLAN ISSUE OR ENDPOINT ISSUE")
    st.stop()

for m in matches:
    st.write("━━━━━━━━━━━━━━")
    st.write(f"{m['away']} vs {m['home']}")
    st.write(m["league"])
    st.write(m["time"])
