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

            if r.status_code != 200:
                continue

            d = r.json()
            if isinstance(d, list):
                for i in d:
                    i["league"] = s
                out.extend(d)

        except:
            continue

    return out

# =========================
# STRENGTH (更真實波動)
# =========================
def strength():
    base = 1.2 + np.random.normal(0, 0.25)
    form = np.random.beta(2, 2)
    return max(0.2, base * (0.7 + form))

# =========================
# SCORE MODEL（修正爆冷分布）
# =========================
def simulate(lh, la):

    home = draw = away = 0
    scores = Counter()

    for _ in range(SIMS):

        # 🔥 variance injection（修正比分集中問題）
        hg = np.random.poisson(max(0.2, lh + np.random.normal(0, 0.4)))
        ag = np.random.poisson(max(0.2, la + np.random.normal(0, 0.4)))

        # ⚡ upset shock
        if np.random.rand() < 0.03:
            hg, ag = ag, hg

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

    return (
        home/total,
        draw/total,
        away/total,
        [fmt(*x) for x in top]
    )

# =========================
# EV / KELLY
# =========================
def EV(p, odds):
    return (p * (odds - 1)) - (1 - p)

def kelly(ev, odds):
    b = odds - 1
    return max(0, min(ev / b, 0.25)) if b > 0 else 0

# =========================
# ⚠️ RISK ENGINE（新增）
# =========================
def risk_score(ev, draw_prob, odds_home, odds_away):

    score = 0

    if draw_prob > 0.28:
        score += 30

    if min(odds_home, odds_away) < 1.6:
        score += 25

    if ev < 0:
        score += 30

    return min(score, 100)

def risk_label(score):

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
st.title("🏦 v8 TRADING SYSTEM (FULL RISK + SCORE + EV)")

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

        lh = strength()
        la = strength()

        ph, pd_, pa, scores = simulate(lh, la)

        evs = {
            "HOME": EV(ph, oh),
            "DRAW": EV(pd_, od),
            "AWAY": EV(pa, oa)
        }

        pick = max(evs, key=evs.get)
        ev = evs[pick]
        odds = {"HOME": oh, "DRAW": od, "AWAY": oa}[pick]

        stake = kelly(ev, odds)

        risk = risk_score(ev, pd_, oh, oa)
        label = risk_label(risk)

        # ================= UI =================
        st.markdown("---")
        st.subheader(f"⚽ {home} vs {away}")
        st.write(f"🕒 台北時間：{k.strftime('%Y-%m-%d %H:%M')}")

        col1, col2, col3, col4 = st.columns(4)

        col1.metric("Pick", pick)
        col2.metric("EV", round(ev, 3))
        col3.metric("Risk", risk)
        col4.metric("Stake", round(stake*100000, 2))

        st.write(f"⚠️ 狀態：{label}")

        st.write("### 📊 比分預測（Top 5）")
        for s in scores:
            st.write("•", s)

    except:
        continue
