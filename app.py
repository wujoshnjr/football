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
                    out.extend(m for m in data)
        except:
            continue

    return out

# =========================
# MARKET SAFE PARSER
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
# LINEUP INTELLIGENCE (NEW)
# =========================
def lineup_factor():
    base = 1.0

    # key injury simulation
    if np.random.rand() < 0.2:
        base -= np.random.uniform(0.05, 0.25)

    # tactical boost
    base += np.random.normal(0, 0.05)

    return max(0.65, min(1.25, base))

# =========================
# HOME ADVANTAGE MODEL (NEW)
# =========================
def home_advantage_factor():
    return 1.0 + np.random.uniform(0.05, 0.15)

def away_penalty():
    return 1.0 - np.random.uniform(0.03, 0.12)

# =========================
# BASE STRENGTH
# =========================
def strength():
    return max(0.2, 1.2 + np.random.normal(0, 0.3))

# =========================
# MONTE CARLO ENGINE
# =========================
def simulate(lh, la, lineup, home_adv):

    home = draw = away = 0
    scores = Counter()

    lh = lh * lineup * home_adv
    la = la * lineup * (2 - home_adv)

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
# EV / KELLY
# =========================
def EV(p, odds):
    return (p * (odds - 1)) - (1 - p)

def kelly(ev, odds):
    b = odds - 1
    return max(0, min(ev / b, 0.25)) if b > 0 else 0

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
# PICK FORMAT
# =========================
def format_pick(pick, home, away):
    if pick == "HOME":
        return f"HOME ({home})"
    if pick == "AWAY":
        return f"AWAY ({away})"
    return "DRAW"

# =========================
# APP
# =========================
st.title("🏦 v16 INSTITUTIONAL HEDGE FUND FINAL SYSTEM")

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

        lineup = lineup_factor()
        home_adv = home_advantage_factor()

        ph, pd_, pa, scores = simulate(lh, la, lineup, home_adv)

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

        pick_text = format_pick(pick, home, away)

        cards.append({
            "time": k,
            "minutes": minutes,
            "match": f"{away} vs {home}",  # 客 vs 主
            "pick": pick_text,
            "ev": ev,
            "risk": risk(ev, pd_, oh, oa),
            "label": label(risk(ev, pd_, oh, oa)),
            "scores": scores
        })

    except:
        continue

# =========================
# SORT (TRADING DESK)
# =========================
cards = sorted(cards, key=lambda x: x["minutes"])

for c in cards:

    st.markdown("━━━━━━━━━━━━━━━━━━")
    st.subheader(c["match"])

    st.write(f"🕒 台北時間：{c['time'].strftime('%Y-%m-%d %H:%M')}")
    st.write(f"⏳ 距離開賽：{int(c['minutes'])} 分鐘")

    col1, col2, col3 = st.columns(3)

    col1.metric("Pick", c["pick"])
    col2.metric("EV", round(c["ev"], 3))
    col3.metric("Risk", c["risk"])

    st.write(f"⚠️ Status: {c['label']}")

    st.write("📊 Score Forecast (Top 5)")
    for s in c["scores"]:
        st.write("•", s)

st.markdown("━━━━━━━━━━━━━━━━━━")
