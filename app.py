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
# SECRETS SAFE LOAD
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
# DATABASE
# =========================
conn = sqlite3.connect("ultra_final.db", check_same_thread=False)
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match TEXT,
    pick TEXT,
    odds REAL,
    edge REAL,
    sim REAL,
    pnl REAL,
    time TEXT
)
""")
conn.commit()

# =========================
# SAFE API CALL
# =========================
def safe_get(url, params=None):
    try:
        r = requests.get(url, params=params, timeout=10)
        try:
            return r.json()
        except:
            return None
    except:
        return None

# =========================
# FIXED SPORT PARSER (IMPORTANT)
# =========================
def get_sport_key():

    url = "https://api.the-odds-api.com/v4/sports"
    raw = safe_get(url, {"apiKey": ODDS_API})

    if raw is None:
        return None

    # CASE 1: dict wrapper
    if isinstance(raw, dict):
        sports = raw.get("data", [])
    # CASE 2: list
    elif isinstance(raw, list):
        sports = raw
    else:
        sports = []

    for s in sports:
        if isinstance(s, dict):
            key = s.get("key", "")
            if "soccer" in key:
                return key

    return None

# =========================
# FETCH MATCHES (FIXED + SAFE)
# =========================
def fetch_matches():

    if not ODDS_API:
        return pd.DataFrame()

    sport_key = get_sport_key()

    if not sport_key:
        st.error("No soccer sport_key found")
        return pd.DataFrame()

    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds"

    raw = safe_get(url, {
        "apiKey": ODDS_API,
        "regions": "eu",
        "markets": "h2h",
        "oddsFormat": "decimal"
    })

    if raw is None:
        return pd.DataFrame()

    if not isinstance(raw, list):
        st.write("DEBUG RAW RESPONSE:", raw)
        return pd.DataFrame()

    rows = []

    for m in raw:
        try:
            if not isinstance(m, dict):
                continue

            home = m.get("home_team")
            away = m.get("away_team")

            bookmakers = m.get("bookmakers", [])
            if not bookmakers:
                continue

            markets = bookmakers[0].get("markets", [])
            if not markets:
                continue

            outcomes = markets[0].get("outcomes", [])
            if len(outcomes) < 2:
                continue

            rows.append({
                "match": f"{home} vs {away}",
                "home_odds": outcomes[0].get("price"),
                "away_odds": outcomes[1].get("price"),
                "time": dt.datetime.now(dt.timezone.utc),
                "taipei": dt.datetime.now(dt.timezone.utc).astimezone(TAIPEI)
            })

        except Exception as e:
            st.write("parse error:", e)
            continue

    return pd.DataFrame(rows)

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
# MONTE CARLO 20K
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
# APP
# =========================
st.title("🏦🔐 vDATA-ENGINEERING ULTRA FINAL")

st.subheader("API STATUS")
st.write(api_status())

df = fetch_matches()

if df.empty:
    st.warning("No data (API issue / rate limit / schema mismatch)")
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
    pnl = stake * sim

    c.execute("""
        INSERT INTO trades (match, pick, odds, edge, sim, pnl, time)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        r["match"],
        pick,
        odds,
        e,
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
        "Stake": round(stake,2),
        "Sim": round(sim,4),
        "PnL": round(pnl,2),
        "Time (Taipei)": r["taipei"]
    })

res = pd.DataFrame(results).sort_values("Edge", ascending=False)

st.subheader("📊 Signals")
st.dataframe(res)

st.subheader("💰 Portfolio")
st.metric("Total PnL", round(res["PnL"].sum(),2))
st.metric("Avg Edge", round(res["Edge"].mean(),4))
st.metric("Trades", len(res))

st.subheader("🌍 System Status")
st.write("✔ Schema-safe API parsing")
st.write("✔ No .get crash risk")
st.write("✔ Streamlit Cloud stable mode")
