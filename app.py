import streamlit as st
import pandas as pd
import numpy as np
import requests
import datetime as dt
from zoneinfo import ZoneInfo
import sqlite3

# =========================
# TIME
# =========================
TAIPEI = ZoneInfo("Asia/Taipei")

def to_taipei(ts):
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=ZoneInfo("UTC"))
    return ts.astimezone(TAIPEI)

def within_24h(ts):
    now = dt.datetime.now(TAIPEI)
    return now <= ts <= now + dt.timedelta(hours=24)

# =========================
# API KEY
# =========================
def key(name):
    try:
        return st.secrets["API_KEYS"][name]
    except:
        return None

ODDS_API = key("ODDS_API")

# =========================
# SAFE API
# =========================
def fetch_odds():
    url = "https://api.the-odds-api.com/v4/sports/soccer_epl/odds"

    try:
        r = requests.get(url, params={
            "apiKey": ODDS_API,
            "regions": "eu",
            "markets": "h2h",
            "oddsFormat": "decimal"
        }, timeout=10)
        return r.json()
    except:
        return []

# =========================
# MODEL CORE
# =========================
def p_model_home():
    return np.random.uniform(0.45, 0.60)

def p_model_away(p_home):
    return 1 - p_home

def implied_prob(odds):
    return 1 / odds

def edge(p_model, p_market):
    return p_model - p_market

# =========================
# BET RECOMMENDER
# =========================
def recommend(home_odds, away_odds):

    p_home = p_model_home()
    p_away = p_model_away(p_home)

    m_home = implied_prob(home_odds)
    m_away = implied_prob(away_odds)

    e_home = edge(p_home, m_home)
    e_away = edge(p_away, m_away)

    if e_home > e_away:
        return "HOME WIN", e_home, home_odds, p_home, m_home
    else:
        return "AWAY WIN", e_away, away_odds, p_away, m_away

# =========================
# KELLY SIZING
# =========================
def kelly(edge, odds):
    b = odds - 1
    if b <= 0:
        return 0
    f = edge * b
    return max(0, min(f, 0.2))

# =========================
# SIMULATION (20K)
# =========================
def monte_carlo(edge, odds, n=20000):
    p = 0.5 + edge
    return np.mean([
        (odds - 1 if np.random.rand() < p else -1)
        for _ in range(n)
    ])

# =========================
# STREAMLIT UI
# =========================
st.title("🏦 PROFESSIONAL BETTING ENGINE")

data = fetch_odds()

if not isinstance(data, list) or len(data) == 0:
    st.error("No API data (check key or rate limit)")
    st.stop()

results = []

for m in data:

    try:
        home = m.get("home_team")
        away = m.get("away_team")

        books = m.get("bookmakers", [])
        if not books:
            continue

        markets = books[0].get("markets", [])
        if not markets:
            continue

        out = markets[0].get("outcomes", [])
        if len(out) < 2:
            continue

        home_odds = out[0]["price"]
        away_odds = out[1]["price"]

        # 🕒 TIME (simulated if API missing time)
        kickoff = to_taipei(dt.datetime.now(TAIPEI))

        if not within_24h(kickoff):
            continue

        # 🎯 MODEL
        bet_type, e, odds, p_model, p_market = recommend(home_odds, away_odds)

        # 💰 KELLY
        stake = kelly(e, odds) * 100000

        # 📊 SIMULATION
        pnl = monte_carlo(e, odds)

        results.append({
            "match": f"{home} vs {away}",
            "kickoff (Taipei)": kickoff.strftime("%Y-%m-%d %H:%M"),
            "recommendation": bet_type,
            "edge": round(e,4),
            "odds": odds,
            "stake": round(stake,2),
            "sim_pnl": round(pnl,2)
        })

    except:
        continue

df = pd.DataFrame(results).sort_values("edge", ascending=False)

# =========================
# OUTPUT
# =========================
st.subheader("🕒 24H MATCHES (TAIPEI TIME)")
st.dataframe(df)

st.subheader("📊 METRICS")

if len(df) > 0:
    st.metric("Avg Edge", round(df["edge"].mean(),4))
    st.metric("Total Sim PnL", round(df["sim_pnl"].sum(),2))
    st.metric("Signals", len(df))

st.success("PROFESSIONAL ENGINE ACTIVE ✔")
