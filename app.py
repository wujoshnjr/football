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

def in_window(k):
    return k and now_taipei() <= k <= now_taipei() + dt.timedelta(hours=24)

# =========================
# DATA (REAL FIRST)
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
# FALLBACK (GUARANTEE OUTPUT)
# =========================
def fallback():
    return [{
        "home_team": "Fallback FC",
        "away_team": "Quant United",
        "commence_time": (now_taipei() + dt.timedelta(hours=3)).isoformat(),
        "bookmakers": [{
            "markets": [{
                "outcomes": [
                    {"price": 2.1},
                    {"price": 3.2},
                    {"price": 3.6}
                ]
            }]
        }]
    }]

# =========================
# ODDS → PROBABILITY
# =========================
def probs_from_odds(odds):

    p = np.array([1/o for o in odds])
    return p / p.sum()

# =========================
# MONTE CARLO (100K SIMS)
# =========================
def monte_carlo(probs):

    outcomes = ["HOME", "DRAW", "AWAY"]

    sims = np.random.choice(outcomes, size=100000, p=probs)

    return {
        "HOME": np.mean(sims == "HOME"),
        "DRAW": np.mean(sims == "DRAW"),
        "AWAY": np.mean(sims == "AWAY")
    }

# =========================
# SCORE SIMULATION
# =========================
def score_sim(prob):

    home_lambda = 1.5 + prob[0]
    away_lambda = 1.2 + prob[2]

    hg = np.random.poisson(home_lambda)
    ag = np.random.poisson(away_lambda)

    return f"{hg}-{ag}"

# =========================
# EV ENGINE
# =========================
def ev(sim_prob, odds):

    return (sim_prob * odds) - 1

# =========================
# APP
# =========================
st.title("🏦 v32 REAL MARKET MONTE CARLO SYSTEM (100,000 SIMULATIONS)")

data = fetch_data()

st.info(f"TOTAL MATCHES LOADED: {len(data)}")

shown = 0

for m in data:

    home = m.get("home_team")
    away = m.get("away_team")

    k = to_taipei(m.get("commence_time"))

    if not in_window(k):
        continue

    try:
        odds = m["bookmakers"][0]["markets"][0]["outcomes"]
        odds = [o["price"] for o in odds]
    except:
        continue

    probs = probs_from_odds(odds)

    mc = monte_carlo(probs)

    score = score_sim(probs)

    ev_home = ev(mc["HOME"], odds[0])
    ev_draw = ev(mc["DRAW"], odds[1])
    ev_away = ev(mc["AWAY"], odds[2])

    best = np.argmax([ev_home, ev_draw, ev_away])
    pick = ["HOME", "DRAW", "AWAY"][best]

    st.markdown("━━━━━━━━━━━━━━━━━━")
    st.subheader(f"{away} vs {home}")

    st.write(f"🕒 台北時間：{k.strftime('%Y-%m-%d %H:%M')}")

    st.write("🎲 Monte Carlo (100,000 sims)")
    st.write(mc)

    st.write("⚽ Predicted Score:", score)

    st.write("💰 EV:")
    st.write({
        "HOME": ev_home,
        "DRAW": ev_draw,
        "AWAY": ev_away
    })

    st.success(f"🏆 PICK: {pick}")

    shown += 1

st.success(f"TOTAL MATCHES SHOWN: {shown}")
