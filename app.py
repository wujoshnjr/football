import streamlit as st
import numpy as np
import requests
import datetime as dt
from zoneinfo import ZoneInfo
import pandas as _pd

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

    all_data = []

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
                all_data.extend(d)

        except:
            continue

    return all_data

# =========================
# FORM / STRENGTH
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
# MONTE CARLO
# =========================
def simulate(lh, la):
    h = d = a = 0

    for _ in range(SIMS):
        hg = np.random.poisson(lh)
        ag = np.random.poisson(la)

        if hg > ag:
            h += 1
        elif hg == ag:
            d += 1
        else:
            a += 1

    return h/SIMS, d/SIMS, a/SIMS

# =========================
# EV / KELLY
# =========================
def EV(p, odds):
    return (p * (odds - 1)) - (1 - p)

def kelly(ev, odds):
    b = odds - 1
    return max(0, min(ev / b, 0.25)) if b > 0 else 0

# =========================
# 💣 REAL UPSET MODEL（核心）
# =========================
def upset_score(ph, p_draw, pa, oh, oa):

    score = 0

    fav_odds = min(oh, oa)

    # 1️⃣ 熱門過熱
    if fav_odds < 1.6:
        score += 0.25

    # 2️⃣ 平局壓力
    if p_draw > 0.27:
        score += 0.2

    # 3️⃣ 模型 vs 市場偏差
    implied_home = 1 / oh
    if abs(ph - implied_home) > 0.15:
        score += 0.2

    # 4️⃣ 客隊爆冷條件
    if pa > 0.30 and oa > 2.8:
        score += 0.25

    return min(score, 1)

# =========================
# 分類
# =========================
def classify(ev, upset, p_draw):

    if upset > 0.5:
        return "🔴 STRONG UPSET", "高機率爆冷"

    if upset > 0.3:
        return "🟠 UPSET", "存在爆冷條件"

    if ev > 0.05:
        return "🟡 VALUE", "模型優勢"

    if p_draw > 0.28:
        return "⚪ DRAW HEAVY", "平局機率高"

    return "🟢 NORMAL", "正常盤"

# =========================
# APP
# =========================
st.title("🏦 REAL UPSET INTELLIGENCE v6")

data = fetch_all()
results = []

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

        lh, la = strength()
        ph, p_draw, pa = simulate(lh, la)

        evs = {
            "HOME": EV(ph, oh),
            "DRAW": EV(p_draw, od),
            "AWAY": EV(pa, oa)
        }

        pick = max(evs, key=evs.get)
        ev = evs[pick]
        odds = {"HOME": oh, "DRAW": od, "AWAY": oa}[pick]

        stake = kelly(ev, odds) * 100000

        upset = upset_score(ph, p_draw, pa, oh, oa)
        label, reason = classify(ev, upset, p_draw)

        results.append({
            "match": f"{home} vs {away}",
            "kickoff": k.strftime("%Y-%m-%d %H:%M"),
            "pick": pick,
            "type": label,
            "reason": reason,
            "EV": round(ev, 4),
            "odds": odds,
            "stake": round(stake, 2),
            "UPSET_SCORE": round(upset, 2)
        })

    except:
        continue

df = _pd.DataFrame.from_records(results)

if df.empty:
    st.warning("沒有比賽")
else:
    df = df.sort_values("EV", ascending=False)
    st.dataframe(df)
