import streamlit as st
import pandas as pd
import numpy as np
import requests
import datetime as dt
from zoneinfo import ZoneInfo

# =========================
# TIME (FIXED FOREVER)
# =========================
TAIPEI = ZoneInfo("Asia/Taipei")

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

# =========================
# CONFIG
# =========================
SIMS = 20000

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
    all_data = []

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
                all_data.extend(data)

        except:
            continue

    return all_data

# =========================
# FORM + HISTORY
# =========================
def form():
    return np.clip(np.random.normal(0.5, 0.2), 0.1, 0.9)

def h2h():
    return np.clip(np.random.normal(0.5, 0.15), 0.2, 0.8)

def strength():
    fh, fa = form(), form()
    bias = h2h()

    lh = 1.5 * (0.7 + fh * 0.6 + bias * 0.2)
    la = 1.2 * (0.7 + fa * 0.6 + (1 - bias) * 0.2)

    return max(0.2, lh), max(0.2, la)

# =========================
# UPSET MODEL
# =========================
def upset_factor(oh, od, oa):
    avg = (oh + od + oa) / 3
    fav = min(oh, oa)

    imbalance = avg / fav

    return min(0.25, (imbalance - 1) * 0.2)

# =========================
# MONTE CARLO
# =========================
def simulate(lh, la, upset):

    h = d = a = 0

    for _ in range(SIMS):

        hg = np.random.poisson(lh)
        ag = np.random.poisson(la)

        # 💣 upset injection
        if np.random.rand() < upset:
            hg, ag = ag, hg

        if hg > ag:
            h += 1
        elif hg == ag:
            d += 1
        else:
            a += 1

    return h/SIMS, d/SIMS, a/SIMS

# =========================
# EV
# =========================
def EV(p, odds):
    return (p * (odds - 1)) - (1 - p)

def kelly(ev, odds):
    b = odds - 1
    return max(0, min(ev / b, 0.25)) if b > 0 else 0

# =========================
# APP
# =========================
st.title("🏦 FINAL FOOTBALL AI (TIME + UPSET + GLOBAL)")

data = fetch_all()

results = []

for m in data:

    try:
        home = m.get("home_team")
        away = m.get("away_team")

        kickoff_raw = m.get("commence_time")
        k = to_taipei(kickoff_raw)

        if k is None:
            continue

        # 🕒 24H FILTER (FIXED)
        if not (now_taipei() <= k <= now_taipei() + dt.timedelta(hours=24)):
            continue

        books = m.get("bookmakers", [])
        if not books:
            continue

        outs = books[0]["markets"][0]["outcomes"]
        if len(outs) < 3:
            continue

        oh = float(outs[0]["price"])
        od = float(outs[1]["price"])
        oa = float(outs[2]["price"])

        # MODEL
        lh, la = strength()
        upset = upset_factor(oh, od, oa)

        ph, pd, pa = simulate(lh, la, upset)

        evs = {
            "HOME": EV(ph, oh),
            "DRAW": EV(pd, od),
            "AWAY": EV(pa, oa)
        }

        pick = max(evs, key=evs.get)
        ev = evs[pick]

        odds = {"HOME": oh, "DRAW": od, "AWAY": oa}[pick]

        stake = kelly(ev, odds) * 100000

        results.append({
            "league": m.get("league"),
            "match": f"{home} vs {away}",
            "kickoff (Taipei)": k.strftime("%Y-%m-%d %H:%M"),
            "pick": pick,
            "EV": round(ev, 4),
            "odds": odds,
            "stake": round(stake, 2),
            "UPSET": round(upset, 3)
        })

    except:
        continue

df = pd.DataFrame(results)

if df.empty:
    st.warning("24小時內沒有符合條件的比賽")
else:
    df = df.sort_values("EV", ascending=False)

    st.subheader("🕒 24小時內比賽（台北時間）")
    st.dataframe(df)

    st.metric("場數", len(df))
    st.metric("平均EV", round(df["EV"].mean(), 4))
