import streamlit as st
import numpy as np
import requests
import datetime as dt
from zoneinfo import ZoneInfo
import pandas as pd
from collections import Counter

TAIPEI = ZoneInfo("Asia/Taipei")

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

# =========================
# FETCH
# =========================
def fetch_all():
    key = st.secrets["API_KEYS"]["ODDS_API"]
    out = []

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
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, list):
                    for m in data:
                        m["league"] = s
                    out.extend(data)
        except:
            continue

    return out

# =========================
# SAFE MARKET
# =========================
def get_outcomes(bookmakers):
    for b in bookmakers:
        for m in b.get("markets", []):
            if m.get("key") == "h2h":
                o = m.get("outcomes", [])
                if len(o) >= 3:
                    return o
    return None

# =========================
# LINEUP ENGINE (NEW)
# =========================
def lineup_factor():
    """
    模擬 lineup / formation / injury impact
    """
    base = 1.0

    # key player missing simulation
    if np.random.rand() < 0.15:
        base -= np.random.uniform(0.05, 0.2)

    # tactical boost
    base += np.random.normal(0, 0.05)

    return max(0.7, min(1.2, base))

def strength():
    return max(0.2, 1.2 + np.random.normal(0, 0.3))

# =========================
# MONTE CARLO (ENHANCED)
# =========================
def simulate(lh, la, lineup_adj):

    home = draw = away = 0
    scores = Counter()

    lh *= lineup_adj
    la *= lineup_adj

    for _ in range(SIMS):

        hg = np.random.poisson(max(0.2, lh + np.random.normal(0, 0.4)))
        ag = np.random.poisson(max(0.2, la + np.random.normal(0, 0.4)))

        scores[(hg, ag)] += 1

        if hg > ag:
            home += 1
        elif hg == ag:
            draw += 1
        else:
            away += 1

    total = SIMS

    top = scores.most_common(5)

    def fmt(s, c):
        return f"{s[0]}-{s[1]} ({round(c/total*100,1)}%)"

    return home/total, draw/total, away/total, [fmt(*x) for x in top]

# =========================
# EV + KELLY
# =========================
def EV(p, odds):
    return (p * (odds - 1)) - (1 - p)

def kelly(ev, odds):
    b = odds - 1
    return max(0, min(ev / b, 0.25)) if b > 0 else 0

# =========================
# INTELLIGENCE SCORE (NEW)
# =========================
def match_intel(lineup_adj, ev, minutes_to_kickoff):

    score = 50

    # lineup stability
    score += (lineup_adj - 1) * 100

    # EV strength
    score += ev * 50

    # kickoff proximity
    if minutes_to_kickoff < 90:
        score += 10

    return max(0, min(100, score))

# =========================
# RISK ENGINE
# =========================
def risk(ev, draw, oh, oa):

    score = 0
    if draw > 0.28:
        score += 25
    if min(oh, oa) < 1.6:
        score += 25
    if ev < 0:
        score += 40
    return min(100, score)

def label(score):
    if score > 70:
        return "🔴 DANGEROUS"
    if score > 45:
        return "🟠 RISKY"
    if score > 20:
        return "🟡 NORMAL"
    return "🟢 SAFE"

# =========================
# APP
# =========================
st.title("🏦 v12 HEDGE FUND + LINEUP INTELLIGENCE SYSTEM")

data = fetch_all()

cards = []

for m in data:

    try:
        home = m.get("home_team")
        away = m.get("away_team")

        k = to_taipei(m.get("commence_time"))
        if not k:
            continue

        if k < now_taipei() - dt.timedelta(hours=2):
            continue

        books = m.get("bookmakers", [])
        if not books:
            continue

        outs = get_outcomes(books)
        if not outs:
            continue

        oh, od, oa = float(outs[0]["price"]), float(outs[1]["price"]), float(outs[2]["price"])

        lh = strength()
        la = strength()

        lineup_adj = lineup_factor()

        ph, pd_, pa, scores = simulate(lh, la, lineup_adj)

        evs = {
            "HOME": EV(ph, oh),
            "DRAW": EV(pd_, od),
            "AWAY": EV(pa, oa)
        }

        pick = max(evs, key=evs.get)
        ev = evs[pick]

        odds = {"HOME": oh, "DRAW": od, "AWAY": oa}[pick]
        stake = kelly(ev, odds)

        minutes = (k - now_taipei()).total_seconds() / 60

        intel = match_intel(lineup_adj, ev, minutes)

        cards.append({
            "time": k,
            "minutes": minutes,
            "match": f"{home} vs {away}",
            "pick": pick,
            "ev": ev,
            "risk": risk(ev, pd_, oh, oa),
            "label": label(risk(ev, pd_, oh, oa)),
            "intel": intel,
            "scores": scores
        })

    except:
        continue

# =========================
# SORT (TRADING DESK)
# =========================
cards = sorted(cards, key=lambda x: x["minutes"])

for c in cards:

    st.markdown("---")
    st.subheader(c["match"])

    st.write(f"🕒 {c['time'].strftime('%Y-%m-%d %H:%M')}")
    st.write(f"⏳ 距離開賽：{int(c['minutes'])} 分鐘")

    col1, col2, col3 = st.columns(3)

    col1.metric("Pick", c["pick"])
    col2.metric("EV", round(c["ev"], 3))
    col3.metric("INTEL", round(c["intel"], 1))

    st.write(f"⚠️ 狀態：{c['label']}")

    st.write("📊 Score forecast:")
    for s in c["scores"]:
        st.write("•", s)
