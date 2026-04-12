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

# =========================
# SECRETS
# =========================
def key(name):
    try:
        return st.secrets["API_KEYS"][name]
    except:
        return None

ODDS_API = key("ODDS_API")

# =========================
# DB
# =========================
conn = sqlite3.connect("core.db", check_same_thread=False)
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
# API
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

            odds = books[0]["markets"][0]["outcomes"]

            rows.append({
                "match": f"{home} vs {away}",
                "time": dt.datetime.now(TAIPEI),
                "home_odds": odds[0]["price"],
                "away_odds": odds[1]["price"]
            })

        except:
            continue

    return pd.DataFrame(rows)

# =========================
# FILTER (24H)
# =========================
def filter_24h(df):
    now = dt.datetime.now(TAIPEI)
    df["time"] = pd.to_datetime(df["time"])
    return df[(df["time"] >= now) & (df["time"] <= now + dt.timedelta(hours=24))]

# =========================
# APL 1 — ALPHA
# =========================
def p_model():
    return np.random.uniform(0.46, 0.54)

def p_market(h, a):
    return (1/h) / ((1/h)+(1/a))

def edge(pm, pk):
    return pm - pk

# =========================
# APL 2 — PORTFOLIO
# =========================
def kelly(edge, odds):
    b = odds - 1
    if b <= 0:
        return 0
    f = (edge * b) / b
    return max(0, min(f, 0.2))

# =========================
# APL 3 — EXECUTION
# =========================
def monte_carlo(edge, odds, n=20000):
    p = 0.5 + edge
    return np.mean([
        (odds - 1 if np.random.rand() < p else -1)
        for _ in range(n)
    ])

# =========================
# BETTING ENGINE
# =========================
def bet(edge, odds, bankroll):
    if edge < 0.01:
        return 0, "NO BET"

    k = kelly(edge, odds)
    stake = bankroll * k * 0.1

    if stake < 1:
        return 0, "TOO SMALL"

    return stake, "BET"

# =========================
# APP
# =========================
st.title("🏦 FINAL INSTITUTIONAL CORE SYSTEM")

df = fetch_matches()

if df.empty:
    st.error("No data available")
    st.stop()

df = filter_24h(df)

if df.empty:
    st.warning("No matches in 24h window")
    st.stop()

BANKROLL = 100000

results = []

for _, r in df.iterrows():

    pm = p_model()
    pk = p_market(r["home_odds"], r["away_odds"])
    e = edge(pm, pk)

    odds = r["home_odds"] if e > 0 else r["away_odds"]

    stake, decision = bet(e, odds, BANKROLL)

    pnl = monte_carlo(e, odds)

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
        "time (Taipei)": r["time"].strftime("%Y-%m-%d %H:%M"),
        "edge": round(e,4),
        "odds": odds,
        "stake": round(stake,2),
        "decision": decision,
        "sim_pnl": round(pnl,2)
    })

out = pd.DataFrame(results).sort_values("edge", ascending=False)

# =========================
# UI
# =========================
st.subheader("🕒 24H MATCHES (TAIPEI TIME)")
st.dataframe(out)

st.subheader("💰 METRICS")
st.metric("Avg Edge", round(out["edge"].mean(),4))
st.metric("Total Sim PnL", round(out["sim_pnl"].sum(),2))
st.metric("Trades", len(out))

st.success("SYSTEM ONLINE ✔")
