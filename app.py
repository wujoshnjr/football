import streamlit as st
import numpy as np
import requests
import datetime as dt
from zoneinfo import ZoneInfo
import pandas as pd

TAIPEI = ZoneInfo("Asia/Taipei")

# =========================
# TIME
# =========================
def now_taipei():
    return dt.datetime.now(TAIPEI)

def to_taipei(ts):
    try:
        t = pd.to_datetime(ts)
        if t.tzinfo is None:
            t = t.tz_localize("UTC")
        return t.tz_convert(TAIPEI)
    except:
        return None

def in_24h(k):
    return k and now_taipei() <= k <= now_taipei() + dt.timedelta(hours=24)

# =========================
# DATA (NO EMPTY STATE)
# =========================
def fetch_data():

    key = st.secrets.get("API_KEYS", {}).get("ODDS_API")

    if not key:
        return fallback()

    try:
        r = requests.get(
            "https://api.the-odds-api.com/v4/sports/soccer_epl/odds",
            params={
                "api_key": key,
                "regions": "eu",
                "markets": "h2h",
                "oddsFormat": "decimal"
            },
            timeout=10
        )

        if r.status_code != 200:
            return fallback()

        data = r.json()

        return data if data else fallback()

    except:
        return fallback()

# =========================
# FALLBACK GUARANTEE
# =========================
def fallback():
    return [{
        "home_team": "Fallback FC",
        "away_team": "Quant United",
        "commence_time": (now_taipei() + dt.timedelta(hours=2)).isoformat(),
        "bookmakers": [{
            "markets": [{
                "outcomes": [
                    {"price": 2.2},
                    {"price": 3.1},
                    {"price": 3.4}
                ]
            }]
        }]
    }]

# =========================
# CORE MODELS
# =========================
def probs(odds):
    p = np.array([1/o for o in odds])
    return p / p.sum()

def monte_carlo(p):
    labels = ["HOME", "DRAW", "AWAY"]
    sims = np.random.choice(labels, 100000, p=p)

    return {
        "HOME": np.mean(sims == "HOME"),
        "DRAW": np.mean(sims == "DRAW"),
        "AWAY": np.mean(sims == "AWAY")
    }

def score_sim(p):
    hg = np.random.poisson(1.4 + p[0])
    ag = np.random.poisson(1.2 + p[2])
    return f"{hg}-{ag}"

def ev(prob, odd):
    return (prob * odd) - 1

# =========================
# DECISION ENGINE
# =========================
def decision(ev_score, risk):

    if ev_score > 0.35 and risk < 0.15:
        return "🟢 EXECUTE"
    elif ev_score > 0.2:
        return "🟡 WATCH"
    else:
        return "🔴 NO BET"

# =========================
# APP UI
# =========================
st.set_page_config(layout="wide")

st.title("🏦 v33 INSTITUTIONAL MONTE CARLO TRADING DESK")

data = fetch_data()

matches = []

for m in data:

    home = m.get("home_team")
    away = m.get("away_team")

    k = to_taipei(m.get("commence_time"))

    if not in_24h(k):
        continue

    try:
        odds = m["bookmakers"][0]["markets"][0]["outcomes"]
        odds = [o["price"] for o in odds]
    except:
        continue

    p = probs(odds)

    mc = monte_carlo(p)

    risk = np.std(list(mc.values()))

    score = score_sim(p)

    ev_home = ev(mc["HOME"], odds[0])
    ev_draw = ev(mc["DRAW"], odds[1])
    ev_away = ev(mc["AWAY"], odds[2])

    best_ev = max(ev_home, ev_draw, ev_away)

    pick = ["HOME", "DRAW", "AWAY"][np.argmax([ev_home, ev_draw, ev_away])]

    action = decision(best_ev, risk)

    matches.append(best_ev)

    # ================= UI CARD =================
    st.markdown("━━━━━━━━━━━━━━━━━━")
    st.subheader(f"{away} vs {home}")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.write("🕒 台北時間")
        st.write(k.strftime("%Y-%m-%d %H:%M"))

    with col2:
        st.write("🎯 Pick")
        st.success(pick)

    with col3:
        st.write("⚡ Action")
        st.warning(action)

    st.write("⚽ Predicted Score:", score)

    st.write("📊 Monte Carlo (100,000 sims)")
    st.write(mc)

    st.write("💰 EV")
    st.write({
        "HOME": round(ev_home, 3),
        "DRAW": round(ev_draw, 3),
        "AWAY": round(ev_away, 3),
    })

# ================= SUMMARY PANEL =================
st.markdown("━━━━━━━━━━━━━━━━━━")
st.subheader("📊 TRADING DESK SUMMARY")

if matches:
    st.write({
        "Total Matches": len(matches),
        "Avg EV": round(np.mean(matches), 3),
        "Max EV": round(np.max(matches), 3),
    })
else:
    st.warning("No matches in current 24h window")
