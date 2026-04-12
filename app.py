import streamlit as st
import pandas as pd
import numpy as np
import requests
import datetime as dt
from zoneinfo import ZoneInfo

# =========================
# TIME
# =========================
TZ = ZoneInfo("Asia/Taipei")

# =========================
# SAFE SECRETS
# =========================
def get_key(name):
    try:
        return st.secrets["API_KEYS"][name]
    except:
        return None

ODDS_API = get_key("ODDS_API")

# =========================
# API CALL
# =========================
def safe_get(url, params=None):
    try:
        r = requests.get(url, params=params, timeout=10)
        return r.json()
    except:
        return None

# =========================
# DATA FETCH
# =========================
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
            bk = m["bookmakers"][0]["markets"][0]["outcomes"]

            rows.append({
                "match": f"{home} vs {away}",
                "home_odds": bk[0]["price"],
                "away_odds": bk[1]["price"]
            })
        except:
            continue

    return pd.DataFrame(rows)

# =========================
# MODEL
# =========================
def p_model():
    return np.random.uniform(0.45, 0.55)

def p_market(h, a):
    return (1/h) / ((1/h)+(1/a))

def edge(pm, pk):
    return pm - pk

# =========================
# CLV
# =========================
def clv(open_odds, close_odds):
    return (1/open_odds) - (1/close_odds)

# =========================
# KELLY
# =========================
def kelly(p, odds):
    b = odds - 1
    return max(0, min((b*p - (1-p))/b, 0.2))

# =========================
# MONTE CARLO 20K
# =========================
def mc(edge, odds, n=20000):
    p = 0.5 + edge
    return np.mean(
        [(odds-1 if np.random.rand()<p else -1) for _ in range(n)]
    )

# =========================
# APP
# =========================
st.title("🏦 FULL CORE HEDGE FUND SYSTEM")

df = fetch_matches()

if df.empty:
    st.error("No data")
    st.stop()

results = []

for _, r in df.iterrows():

    pm = p_model()
    pk = p_market(r["home_odds"], r["away_odds"])
    e = edge(pm, pk)

    pick_odds = r["home_odds"] if e > 0 else r["away_odds"]

    p = 0.5 + e
    size = kelly(p, pick_odds)

    sim = mc(e, pick_odds)

    results.append({
        "match": r["match"],
        "edge": round(e,4),
        "odds": pick_odds,
        "kelly": round(size,4),
        "simulation_pnl": round(sim,2)
    })

df_out = pd.DataFrame(results).sort_values("edge", ascending=False)

# =========================
# UI
# =========================
st.subheader("📊 SIGNALS")
st.dataframe(df_out)

st.subheader("💰 PORTFOLIO")
st.metric("Avg Edge", round(df_out["edge"].mean(),4))
st.metric("Total Sim PnL", round(df_out["simulation_pnl"].sum(),2))

st.success("CORE ENGINE RUNNING ✔")
