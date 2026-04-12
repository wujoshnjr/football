import streamlit as st
import numpy as np
import requests
import datetime as dt
from zoneinfo import ZoneInfo
import pandas as _pd
from collections import Counter

# =========================
# TIME
# =========================
TAIPEI = ZoneInfo("Asia/Taipei")

def now_taipei():
    return dt.datetime.now(TAIPEI)

def to_taipei(ts):
    try:
        t = _pd.to_datetime(ts)
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
    try:
        key = st.secrets["API_KEYS"]["ODDS_API"]
    except:
        return []

    data = []

    for s in SPORTS:
        try:
            r = requests.get(
                f"https://api.the-odds-api.com/v4/sports/{s}/odds",
                params={
                    "api_key": key,
                    "regions": "eu",
                    "markets": "h2h",
                    "oddsFormat": "decimal"
                },
                timeout=10
            )

            if r.status_code != 200:
                continue

            d = r.json()
            if isinstance(d, list):
                for i in d:
                    i["league"] = s
                data.extend(d)

        except:
            continue

    return data

# =========================
# MODEL
# =========================
def team_strength():
    base = 1.3 + np.random.normal(0, 0.2)
    form = np.clip(np.random.normal(0.5, 0.15), 0.2, 0.8)
    return base * (0.8 + form)

def simulate_match(lh, la):

    home = draw = away = 0
    scores = Counter()

    for _ in range(SIMS):

        hg = np.random.poisson(lh)
        ag = np.random.poisson(la)

        scores[(hg, ag)] += 1

        if hg > ag:
            home += 1
        elif hg == ag:
            draw += 1
        else:
            away += 1

    total = SIMS

    top = scores.most_common(3)

    def fmt(s, c):
        return f"{s[0]}-{s[1]} ({round(c/total*100,1)}%)"

    return (
        home/total,
        draw/total,
        away/total,
        fmt(*top[0]) if len(top) > 0 else "-",
        fmt(*top[1]) if len(top) > 1 else "-",
        fmt(*top[2]) if len(top) > 2 else "-"
    )

# =========================
# BETTING LOGIC
# =========================
def EV(p, odds):
    return (p * (odds - 1)) - (1 - p)

def kelly(ev, odds):
    b = odds - 1
    return max(0, min(ev / b, 0.25)) if b > 0 else 0

def recommend(p_home, p_draw, p_away, scores):

    total_goals = []
    btts_yes = 0

    for s in scores:
        hg, ag = s
        total_goals.append(hg + ag)
        if hg > 0 and ag > 0:
            btts_yes += 1

    avg_goals = np.mean(total_goals) if total_goals else 2.5
    btts_prob = btts_yes / len(scores) if scores else 0.5

    ou = "OVER 2.5" if avg_goals > 2.5 else "UNDER 2.5"
    btts = "BTTS YES" if btts_prob > 0.5 else "BTTS NO"

    return ou, btts

# =========================
# APP UI
# =========================
st.title("🏦 FOOTBALL AI v7.5（PRO UI + BETTING ENGINE）")

data = fetch_all()

for m in data:

    try:
        home = m.get("home_team")
        away = m.get("away_team")

        k = to_taipei(m.get("commence_time"))

        if not k or not (now_taipei() <= k <= now_taipei() + dt.timedelta(hours=24)):
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

        lh = team_strength()
        la = team_strength()

        ph, pd_, pa, s1, s2, s3 = simulate_match(lh, la)

        evs = {
            "HOME": EV(ph, oh),
            "DRAW": EV(pd_, od),
            "AWAY": EV(pa, oa)
        }

        pick = max(evs, key=evs.get)
        ev = evs[pick]
        odds = {"HOME": oh, "DRAW": od, "AWAY": oa}[pick]
        stake = kelly(ev, odds)

        # UI CARD
        st.markdown("---")
        st.subheader(f"⚽ {home} vs {away}")
        st.write(f"🕒 台北時間：{k.strftime('%Y-%m-%d %H:%M')}")

        col1, col2, col3 = st.columns(3)

        col1.metric("推薦", pick)
        col2.metric("EV", round(ev, 3))
        col3.metric("Stake", round(stake*100000, 2))

        st.write("### 📊 預測比分")
        st.write(f"🥇 {s1}")
        st.write(f"🥈 {s2}")
        st.write(f"🥉 {s3}")

    except:
        continue
