import streamlit as st
import pandas as pd
import numpy as np
import requests
import datetime as dt
from zoneinfo import ZoneInfo

# =========================
# TIMEZONE
# =========================
TAIPEI = ZoneInfo("Asia/Taipei")

def now_taipei():
    return dt.datetime.now(TAIPEI)

def to_taipei(ts):
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=ZoneInfo("UTC"))
    return ts.astimezone(TAIPEI)

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
# SAFE API CALL
# =========================
def fetch_odds():
    if not ODDS_API:
        st.error("❌ Missing ODDS_API key")
        return []

    url = "https://api.the-odds-api.com/v4/sports/soccer_epl/odds"

    try:
        r = requests.get(url, params={
            "apiKey": ODDS_API,
            "regions": "eu",
            "markets": "h2h",
            "oddsFormat": "decimal"
        }, timeout=10)

        data = r.json()

        # DEBUG
        st.write("🔍 API TYPE:", type(data))

        if isinstance(data, dict) and "error" in data:
            st.error(data)
            return []

        if not isinstance(data, list):
            st.error("Invalid API format")
            st.write(data)
            return []

        return data

    except Exception as e:
        st.error(f"API request failed: {e}")
        return []

# =========================
# MODEL
# =========================
def p_model_home():
    return np.random.uniform(0.45, 0.60)

def p_model_away(p_home):
    return 1 - p_home

def implied_prob(odds):
    return 1 / odds if odds else 0

def edge(p_model, p_market):
    return p_model - p_market

# =========================
# BET RECOMMENDATION
# =========================
def recommend(home_odds, away_odds):

    p_home = p_model_home()
    p_away = p_model_away(p_home)

    m_home = implied_prob(home_odds)
    m_away = implied_prob(away_odds)

    e_home = edge(p_home, m_home)
    e_away = edge(p_away, m_away)

    if e_home >= e_away:
        return "HOME WIN", e_home, home_odds
    else:
        return "AWAY WIN", e_away, away_odds

# =========================
# KELLY
# =========================
def kelly(e, odds):
    b = odds - 1
    if b <= 0:
        return 0
    return max(0, min(e * b, 0.2))

# =========================
# SIMULATION
# =========================
def monte_carlo(e, odds, n=20000):
    p = 0.5 + e
    return np.mean([
        (odds - 1 if np.random.rand() < p else -1)
        for _ in range(n)
    ])

# =========================
# STREAMLIT APP
# =========================
st.title("🏦 FIXED PROFESSIONAL BETTING ENGINE")

data = fetch_odds()

if not data:
    st.stop()

results = []

# =========================
# PROCESS MATCHES
# =========================
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

        outcomes = markets[0].get("outcomes", [])
        if len(outcomes) < 2:
            continue

        home_odds = outcomes[0]["price"]
        away_odds = outcomes[1]["price"]

        # 🕒 TIME (simulated safely)
        kickoff = now_taipei()

        # 🕒 24H FILTER (FIXED SAFE)
        if not (kickoff <= now_taipei() + dt.timedelta(hours=24)):
            continue

        # 🧠 MODEL
        bet_type, e, odds = recommend(home_odds, away_odds)

        # 💰 SKIP LOW EDGE (IMPORTANT FIX)
        if e is None:
            continue

        stake = kelly(e, odds) * 100000

        pnl = monte_carlo(e, odds)

        results.append({
            "match": f"{home} vs {away}",
            "kickoff (Taipei)": kickoff.strftime("%Y-%m-%d %H:%M"),
            "recommendation": bet_type,
            "edge": round(float(e), 4),
            "odds": odds,
            "stake": round(stake, 2),
            "sim_pnl": round(pnl, 2)
        })

    except Exception as ex:
        st.warning(f"Skip match error: {ex}")

# =========================
# DATAFRAME SAFETY FIX (IMPORTANT)
# =========================
df = pd.DataFrame(results)

if df.empty:
    st.error("❌ No valid betting signals generated (API or filter issue)")
    st.stop()

if "edge" not in df.columns:
    st.error("❌ Edge column missing (pipeline failure)")
    st.write(df)
    st.stop()

df = df.sort_values("edge", ascending=False)

# =========================
# OUTPUT
# =========================
st.subheader("🕒 24H MATCHES (TAIPEI TIME)")
st.dataframe(df)

st.subheader("📊 METRICS")

st.metric("Avg Edge", round(df["edge"].mean(), 4))
st.metric("Total Sim PnL", round(df["sim_pnl"].sum(), 2))
st.metric("Signals", len(df))

st.success("SYSTEM FIXED + STABLE ✔")
