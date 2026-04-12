import streamlit as st
import pandas as pd
import numpy as np
import requests
import datetime as dt
from zoneinfo import ZoneInfo
import sqlite3

# =========================
# TIME CONFIG
# =========================
TAIPEI = ZoneInfo("Asia/Taipei")

# =========================
# SAFE SECRETS
# =========================
def key(name):
    try:
        return st.secrets["API_KEYS"][name]
    except:
        return None

ODDS_API = key("ODDS_API")

# =========================
# DB (Execution Layer)
# =========================
conn = sqlite3.connect("institutional.db", check_same_thread=False)
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match TEXT,
    edge REAL,
    stake REAL,
    pnl REAL,
    time TEXT
)
""")
conn.commit()

# =========================
# DATA LAYER
# =========================
def safe_get(url, params=None):
    try:
        return requests.get(url, params=params, timeout=10).json()
    except:
        return None

def fetch_matches():
    if not ODDS_API:
        return pd.DataFrame()

    url = "https://api.the-odds-api.com/v4/sports/soccer_epl/odds"

    data = safe_get(url, {
        "apiKey": ODDS_API,
        "regions": "eu",
        "markets": "h2h",
        "oddsFormat": "decimal"
    })

    if not isinstance(data, list):
        return pd.DataFrame()

    rows = []

    for m in data:
        try:
            home = m["home_team"]
            away = m["away_team"]

            books = m.get("bookmakers", [])
            if not books:
                continue

            outcomes = books[0]["markets"][0]["outcomes"]

            rows.append({
                "match": f"{home} vs {away}",
                "home_odds": outcomes[0]["price"],
                "away_odds": outcomes[1]["price"],
                "time": dt.datetime.now(TAIPEI)
            })
        except:
            continue

    return pd.DataFrame(rows)

# =========================
# APL 1 — ALPHA ENGINE
# =========================
def p_model():
    return np.random.uniform(0.46, 0.54)

def p_market(h, a):
    return (1/h) / ((1/h)+(1/a))

def edge(pm, pk):
    return pm - pk

# =========================
# APL 2 — PORTFOLIO ENGINE
# =========================
def kelly(p, odds):
    b = odds - 1
    if b <= 0:
        return 0
    f = (b*p - (1-p)) / b
    return max(0, min(f, 0.2))

# =========================
# APL 3 — EXECUTION ENGINE
# =========================
def simulate(edge, odds, n=20000):
    p = 0.5 + edge
    return np.mean([
        (odds - 1 if np.random.rand() < p else -1)
        for _ in range(n)
    ])

# =========================
# APP
# =========================
st.title("🏦 FINAL REBUILD — INSTITUTIONAL CORE")

df = fetch_matches()

if df.empty:
    st.error("No data (API / key / region issue)")
    st.stop()

results = []

BANKROLL = 100000

for _, r in df.iterrows():

    # APL 1
    pm = p_model()
    pk = p_market(r["home_odds"], r["away_odds"])
    e = edge(pm, pk)

    pick_odds = r["home_odds"] if e > 0 else r["away_odds"]

    # APL 2
    k = kelly(0.5 + e, pick_odds)
    stake = BANKROLL * k * 0.1

    # APL 3
    pnl = simulate(e, pick_odds)

    c.execute("""
        INSERT INTO trades (match, edge, stake, pnl, time)
        VALUES (?, ?, ?, ?, ?)
    """, (
        r["match"],
        float(e),
        float(stake),
        float(pnl),
        dt.datetime.now(TAIPEI).isoformat()
    ))
    conn.commit()

    results.append({
        "match": r["match"],
        "edge": round(e,4),
        "odds": pick_odds,
        "stake": round(stake,2),
        "sim_pnl": round(pnl,2)
    })

out = pd.DataFrame(results).sort_values("edge", ascending=False)

# =========================
# DASHBOARD
# =========================
st.subheader("📊 SIGNALS")
st.dataframe(out)

st.subheader("💰 PERFORMANCE")

st.metric("Avg Edge", round(out["edge"].mean(),4))
st.metric("Total Sim PnL", round(out["sim_pnl"].sum(),2))
st.metric("Trades", len(out))

st.success("INSTITUTIONAL CORE RUNNING ✔")
