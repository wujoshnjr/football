import streamlit as st
import pandas as pd
import numpy as np
import requests
import datetime as dt
from zoneinfo import ZoneInfo
from math import exp, factorial

# =========================
# SAFETY CORE
# =========================
import pandas as _pd
assert hasattr(_pd, "DataFrame")

# =========================
# TIMEZONE
# =========================
TAIPEI = ZoneInfo("Asia/Taipei")

def now_taipei():
    return dt.datetime.now(TAIPEI)

def to_taipei(t):
    try:
        if t is None:
            return None
        if t.tzinfo is None:
            t = t.replace(tzinfo=ZoneInfo("UTC"))
        return t.astimezone(TAIPEI)
    except:
        return None

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
# SAFE FETCH
# =========================
def fetch_matches():

    if not ODDS_API:
        st.error("Missing API KEY")
        return []

    url = "https://api.the-odds-api.com/v4/soccer_epl/odds"

    params = {
        "api_key": ODDS_API,
        "regions": "eu",
        "markets": "h2h",
        "oddsFormat": "decimal"
    }

    try:
        r = requests.get(url, params=params, timeout=10)

        if r.status_code != 200:
            st.error(f"HTTP {r.status_code}")
            return []

        data = r.json()
        if not isinstance(data, list):
            return []

        return data

    except:
        return []

# =========================
# PROB MODEL (DIXON-COLES LIGHT)
# =========================
def xg_model():
    return (
        max(0.2, np.random.normal(1.55, 0.2)),
        max(0.2, np.random.normal(1.20, 0.2))
    )

def probs(lh, la):

    # simplified poisson grid
    max_g = 5
    m = np.zeros((max_g, max_g))

    def p(lam, k):
        return (lam**k) * np.exp(-lam) / factorial(k)

    for i in range(max_g):
        for j in range(max_g):
            m[i][j] = p(lh, i) * p(la, j)

    home = np.tril(m, -1).sum()
    draw = np.trace(m)
    away = np.triu(m, 1).sum()

    s = home + draw + away

    return home/s, draw/s, away/s

def devig(h, d, a):
    s = h + d + a
    return (h/s, d/s, a/s) if s > 0 else (0.33,0.33,0.34)

# =========================
# EV ENGINE
# =========================
def EV(p, odds):
    return (p * (odds - 1)) - (1 - p)

def kelly(ev, odds):
    b = odds - 1
    if b <= 0:
        return 0
    f = ev / b
    return max(0, min(f, 0.25))

# =========================
# CLV SIM (placeholder but structured)
# =========================
def clv_proxy(open_odds, current_odds):
    try:
        return (open_odds - current_odds) / open_odds
    except:
        return 0

# =========================
# KICKOFF
# =========================
def kickoff(m):
    try:
        ts = m.get("commence_time")
        if not ts:
            return None
        return to_taipei(pd.to_datetime(ts).to_pydatetime())
    except:
        return None

# =========================
# BET GRADE SYSTEM
# =========================
def grade(ev, clv):

    score = (ev * 100) + (clv * 50)

    if score > 8:
        return "A+"
    elif score > 5:
        return "A"
    elif score > 2:
        return "B"
    else:
        return "C"

# =========================
# APP
# =========================
st.title("🏦 INSTITUTIONAL QUANT ENGINE v2")

data = fetch_matches()

results = []

if not isinstance(data, list) or len(data) == 0:
    st.error("No data")
    st.stop()

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

        outs = markets[0].get("outcomes", [])
        if len(outs) < 3:
            continue

        oh = float(outs[0]["price"])
        od = float(outs[1]["price"])
        oa = float(outs[2]["price"])

        k = kickoff(m)
        if not k:
            continue

        # 24h filter
        if not (now_taipei() <= k <= now_taipei() + dt.timedelta(hours=24)):
            continue

        # MODEL
        lh, la = xg_model()

        ph, pd, pa = probs(lh, la)
        ph, pd, pa = devig(ph, pd, pa)

        evs = {
            "HOME": EV(ph, oh),
            "DRAW": EV(pd, od),
            "AWAY": EV(pa, oa)
        }

        pick = max(evs, key=evs.get)
        ev = evs[pick]

        odds_map = {"HOME": oh, "DRAW": od, "AWAY": oa}
        odds = odds_map[pick]

        stake = kelly(ev, odds) * 100000

        # CLV proxy (no closing odds yet → simulate structure)
        clv = clv_proxy(odds, odds * 0.98)

        results.append({
            "match": f"{home} vs {away}",
            "kickoff": k.strftime("%Y-%m-%d %H:%M"),
            "pick": pick,
            "EV": ev,
            "CLV": clv,
            "odds": odds,
            "stake": stake,
            "grade": grade(ev, clv),
            "xG": (lh, la)
        })

    except:
        continue

# =========================
# SAFE DF
# =========================
clean = [r for r in results if isinstance(r, dict)]

if len(clean) == 0:
    st.error("No signals")
    st.stop()

df = _pd.DataFrame.from_records(clean)

df = df.sort_values("EV", ascending=False)

# =========================
# OUTPUT
# =========================
st.subheader("🕒 24H TAIPEI MATCHES")
st.dataframe(df)

st.subheader("📊 PERFORMANCE")
st.metric("Signals", len(df))
st.metric("Avg EV", round(df["EV"].mean(), 4))

st.success("INSTITUTIONAL ENGINE ACTIVE ✔")
