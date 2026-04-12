import streamlit as st
import pandas as pd
import numpy as np
import requests
import sqlite3
import datetime as dt
from zoneinfo import ZoneInfo
import random

# =========================
# TIMEZONE
# =========================
TAIPEI = ZoneInfo("Asia/Taipei")

# =========================
# SECRETS
# =========================
def get_key(name):
    try:
        return st.secrets["API_KEYS"].get(name)
    except:
        return None

ODDS_API = get_key("ODDS_API")
SPORTMONKS = get_key("SPORTMONKS")
NEWS_API = get_key("NEWS_API")

# =========================
# API STATUS
# =========================
def api_status():
    return {
        "ODDS API": "🟢" if ODDS_API else "🔴",
        "SPORTMONKS": "🟡" if SPORTMONKS else "🔴",
        "NEWS API": "🟡" if NEWS_API else "🔴",
    }

# =========================
# DB
# =========================
conn = sqlite3.connect("ultra_fixed.db", check_same_thread=False)
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match TEXT,
    pick TEXT,
    odds REAL,
    edge REAL,
    clv REAL,
    sim REAL,
    pnl REAL,
    time TEXT
)
""")
conn.commit()

# =========================
# SAFE FETCH MATCHES (FIXED)
# =========================
def fetch_matches():

    if not ODDS_API:
        return pd.DataFrame()

    try:
        # 1️⃣ GET SPORT LIST
        sports_url = "https://api.the-odds-api.com/v4/sports"
        sports = requests.get(
            sports_url,
            params={"apiKey": ODDS_API},
            timeout=10
        ).json()

        sport_key = None
        for s in sports:
            if "soccer" in s.get("key", ""):
                sport_key = s["key"]
                break

        if not sport_key:
            st.error("No soccer sport_key found")
            return pd.DataFrame()

        # 2️⃣ GET ODDS
        url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds"

        r = requests.get(url, params={
            "apiKey": ODDS_API,
            "regions": "eu",
            "markets": "h2h",
            "oddsFormat": "decimal"
        }, timeout=10)

        # 🔍 DEBUG (IMPORTANT)
        st.write("API STATUS:", r.status_code)

        try:
            data = r.json()
        except:
            st.error("Invalid JSON from API")
            return pd.DataFrame()

        if not isinstance(data, list):
            st.write("RAW RESPONSE:", data)
            return pd.DataFrame()

        rows = []

        for m in data:
            try:
                home = m["home_team"]
                away = m["away_team"]

                bookmakers = m.get("bookmakers", [])
                if not bookmakers:
                    continue

                outcomes = bookmakers[0]["markets"][0]["outcomes"]

                rows.append({
                    "match": f"{home} vs {away}",
                    "home_odds": outcomes[0]["price"],
                    "away_odds": outcomes[1]["price"],
                    "time": dt.datetime.now(dt.timezone.utc),
                    "taipei": dt.datetime.now(dt.timezone.utc).astimezone(TAIPEI)
                })

            except:
                continue

        return pd.DataFrame(rows)

    except Exception as e:
        st.error(f"Fetch error: {e}")
        return pd.DataFrame()

# =========================
# MODEL
# =========================
def p_model():
    return np.random.uniform(0.45, 0.55)

def p_market(h, a):
    try:
        return (1/h) / ((1/h)+(1/a))
    except:
        return 0.5

def edge(pm, pk):
    return pm - pk

# =========================
# CLV
# =========================
def clv(open_odds, close_odds):
    try:
        return (close_odds - open_odds) / open_odds
    except:
        return 0

# =========================
# KELLY
# =========================
def kelly(e, odds):
    if odds is None:
        return 0
    b = odds - 1
    p = 0.5 + e
    if b <= 0:
        return 0
    f = (b*p - (1-p)) / b
    return max(0, min(f, 0.25))

# =========================
# MONTE CARLO (20K)
# =========================
def monte_carlo(e, odds, n=20000):
    if odds is None:
        return 0
    p = 0.5 + e
    return np.mean([
        (odds - 1 if random.random() < p else -1)
        for _ in range(n)
    ])

# =========================
# APP
# =========================
st.title("🏦🔐 vCLOUD FIXED ULTRA FINAL")

st.subheader("API STATUS")
st.write(api_status())

df = fetch_matches()

if df.empty:
    st.warning("No data returned from API (check key or rate limit)")
    st.stop()

results = []

for _, r in df.iterrows():

    pm = p_model()
    pk = p_market(r["home_odds"], r["away_odds"])
    e = edge(pm, pk)

    pick = "home" if e > 0 else "away"
    odds = r["home_odds"] if pick == "home" else r["away_odds"]

    stake = kelly(e, odds) * 10000
    sim = monte_carlo(e, odds)

    clv_value = clv(odds, odds * np.random.uniform(0.95, 1.05))
    pnl = stake * sim

    c.execute("""
        INSERT INTO trades (match, pick, odds, edge, clv, sim, pnl, time)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        r["match"],
        pick,
        odds,
        e,
        clv_value,
        sim,
        pnl,
        dt.datetime.now(TAIPEI).isoformat()
    ))
    conn.commit()

    results.append({
        "Match": r["match"],
        "Pick": pick,
        "Odds": odds,
        "Edge": round(e,4),
        "CLV": round(clv_value,4),
        "Stake": round(stake,2),
        "PnL": round(pnl,2),
        "Time": r["taipei"]
    })

res = pd.DataFrame(results).sort_values("Edge", ascending=False)

st.subheader("📊 Signals")
st.dataframe(res)

st.subheader("💰 Metrics")
st.metric("Total PnL", round(res["PnL"].sum(),2))
st.metric("Avg Edge", round(res["Edge"].mean(),4))
st.metric("Avg CLV", round(res["CLV"].mean(),4))

st.subheader("🌍 Exposure")
st.write("Matches loaded:", len(res))
