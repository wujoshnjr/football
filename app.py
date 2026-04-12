import streamlit as st
import pandas as pd
import numpy as np
import requests
import datetime as dt
from zoneinfo import ZoneInfo

# =========================
# SAFETY
# =========================
import pandas as _pd
assert hasattr(_pd, "DataFrame")

TAIPEI = ZoneInfo("Asia/Taipei")

SIMS = 20000

# =========================
# GLOBAL LEAGUES
# =========================
SPORTS = [
    "soccer_epl",
    "soccer_uefa_champs_league",
    "soccer_spain_la_liga",
    "soccer_italy_serie_a",
    "soccer_germany_bundesliga",
    "soccer_france_ligue_one",
    "soccer_usa_mls"
]

# =========================
# FETCH
# =========================
def fetch_all():

    key = st.secrets["API_KEYS"]["ODDS_API"]
    out = []

    for s in SPORTS:

        url = f"https://api.the-odds-api.com/v4/sports/{s}/odds"

        try:
            r = requests.get(url, params={
                "api_key": key,
                "regions": "eu",
                "markets": "h2h",
                "oddsFormat": "decimal"
            }, timeout=10)

            if r.status_code != 200:
                continue

            data = r.json()
            if isinstance(data, list):
                for d in data:
                    d["league"] = s
                out.extend(data)

        except:
            continue

    return out

# =========================
# 🧠 FORM
# =========================
def form():
    return np.clip(np.random.normal(0.5, 0.2), 0.1, 0.9)

def h2h():
    return np.clip(np.random.normal(0.5, 0.15), 0.2, 0.8)

# =========================
# ⚽ BASE STRENGTH
# =========================
def base_strength():

    lh = 1.5
    la = 1.2

    fh = form()
    fa = form()

    bias = h2h()

    return (
        lh * (0.7 + fh * 0.6 + bias * 0.2),
        la * (0.7 + fa * 0.6 + (1 - bias) * 0.2)
    )

# =========================
# 💣 UPSET ENGINE (NEW CORE)
# =========================
def upset_probability(ph, pd, pa, odds_home, odds_draw, odds_away):

    # market imbalance (favorite trap)
    fav = max(odds_home, odds_away)
    imbalance = fav / np.mean([odds_home, odds_draw, odds_away])

    # high imbalance → more upset chance
    upset_bias = min(0.25, (imbalance - 1) * 0.15)

    # draw increases chaos
    chaos = pd * 0.5

    return upset_bias + chaos

# =========================
# 🎲 MONTE CARLO WITH UPSET INJECTION
# =========================
def simulate(lh, la, upset):

    home = draw = away = 0

    for _ in range(SIMS):

        hg = np.random.poisson(lh)
        ag = np.random.poisson(la)

        # 💣 upset injection (random shock events)
        if np.random.rand() < upset:
            hg, ag = ag, hg  # flip result (major upset)

        if hg > ag:
            home += 1
        elif hg == ag:
            draw += 1
        else:
            away += 1

    return home/SIMS, draw/SIMS, away/SIMS

# =========================
# EV + KELLY
# =========================
def EV(p, odds):
    return (p * (odds - 1)) - (1 - p)

def kelly(ev, odds):
    b = odds - 1
    if b <= 0:
        return 0
    return max(0, min(ev / b, 0.25))

# =========================
# APP
# =========================
st.title("🏦 HEDGE FUND CORE v5 (UPSET-AWARE MODEL)")

data = fetch_all()

results = []

for m in data:

    try:
        home = m.get("home_team")
        away = m.get("away_team")

        books = m.get("bookmakers", [])
        if not books:
            continue

        outs = books[0]["markets"][0]["outcomes"]
        if len(outs) < 3:
            continue

        oh = float(outs[0]["price"])
        od = float(outs[1]["price"])
        oa = float(outs[2]["price"])

        # =========================
        # MODEL BASE
        # =========================
        lh, la = base_strength()

        # baseline probabilities
        ph = 0.45
        pd = 0.25
        pa = 0.30

        # 💣 upset probability engine
        upset = upset_probability(ph, pd, pa, oh, od, oa)

        # 🎲 simulate with upset risk
        ph, pd, pa = simulate(lh, la, upset)

        ev_map = {
            "HOME": EV(ph, oh),
            "DRAW": EV(pd, od),
            "AWAY": EV(pa, oa)
        }

        pick = max(ev_map, key=ev_map.get)

        odds = {"HOME": oh, "DRAW": od, "AWAY": oa}[pick]

        ev = ev_map[pick]

        stake = kelly(ev, odds) * 100000

        results.append({
            "match": f"{home} vs {away}",
            "pick": pick,
            "P_home": ph,
            "P_draw": pd,
            "P_away": pa,
            "UPSET_RISK": upset,
            "EV": ev,
            "odds": odds,
            "stake": stake
        })

    except:
        continue

# =========================
# OUTPUT
# =========================
df = _pd.DataFrame.from_records(results)

if df.empty:
    st.warning("No signals")
    st.stop()

df = df.sort_values("EV", ascending=False)

st.subheader("🌍 UPSET-AWARE SIGNALS (GLOBAL)")
st.dataframe(df)

st.metric("Signals", len(df))
st.metric("Avg EV", round(df["EV"].mean(), 4))

st.success("UPSET-AWARE HEDGE FUND CORE ACTIVE ✔")
