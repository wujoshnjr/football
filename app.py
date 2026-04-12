import streamlit as st
import requests
import pandas as pd
import numpy as np
import datetime as dt
from zoneinfo import ZoneInfo

TAIPEI = ZoneInfo("Asia/Taipei")

# =========================
# GLOBAL LEAGUES
# =========================
SPORTS = [
    "soccer_epl",
    "soccer_spain_la_liga",
    "soccer_italy_serie_a",
    "soccer_germany_bundesliga",
    "soccer_france_ligue_one",
    "soccer_usa_mls"
]

# =========================
# TIME
# =========================
def now():
    return dt.datetime.now(TAIPEI)

def to_taipei(ts):
    try:
        t = pd.to_datetime(ts)
        if t.tzinfo is None:
            t = t.tz_localize("UTC")
        return t.tz_convert(TAIPEI)
    except:
        return None

def in_24h(t):
    return now() <= t <= now() + dt.timedelta(hours=24)

# =========================
# FETCH GLOBAL ODDS
# =========================
def fetch_all_odds():

    key = st.secrets["API_KEYS"]["ODDS_API"]
    all_matches = []

    for sport in SPORTS:

        url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds"

        r = requests.get(url, params={
            "api_key": key,
            "regions": "eu",
            "markets": "h2h"
        })

        if r.status_code != 200:
            continue

        try:
            data = r.json()
            all_matches.extend(data)
        except:
            continue

    return all_matches

# =========================
# FALLBACK（多場）
# =========================
def fallback():

    return [
        {"home":"Team A","away":"Team B","time":"2026-04-12T18:00:00Z","odds":[2.1,3.2,3.5]},
        {"home":"Team C","away":"Team D","time":"2026-04-12T20:00:00Z","odds":[1.9,3.4,4.0]},
        {"home":"Team E","away":"Team F","time":"2026-04-13T01:00:00Z","odds":[2.5,3.1,2.8]}
    ]

# =========================
# NORMALIZE
# =========================
def normalize(data):

    matches = []

    for m in data:

        home = m.get("home_team") or m.get("home")
        away = m.get("away_team") or m.get("away")
        time = m.get("commence_time") or m.get("time")

        if not home or not away:
            continue

        kickoff = to_taipei(time)
        if not kickoff:
            continue

        if not in_24h(kickoff):
            continue

        try:
            outcomes = m["bookmakers"][0]["markets"][0]["outcomes"]
            odds = [o["price"] for o in outcomes]
        except:
            odds = m.get("odds")

        if not odds:
            continue

        matches.append({
            "home": home,
            "away": away,
            "time": kickoff,
            "odds": odds
        })

    return matches

# =========================
# MODEL
# =========================
def market_prob(odds):
    inv = [1/o for o in odds]
    s = sum(inv)
    return [x/s for x in inv]

def adjust(mp):
    noise = np.random.normal(0,0.05,3)
    upset = np.random.uniform(-0.1,0.1)

    p = [
        mp[0] + noise[0] + upset,
        mp[1] + noise[1],
        mp[2] + noise[2] - upset
    ]

    p = np.clip(p,0.01,0.98)
    s = sum(p)
    return [x/s for x in p]

def simulate(p, n=100000):
    res = np.random.choice([0,1,2], size=n, p=p)
    return np.bincount(res, minlength=3)/n

def ev(prob, odds):
    return prob * odds - 1

def trap(model_p, market_p):

    if market_p[0] > 0.6 and model_p[0] < 0.5:
        return "⚠️ 主隊陷阱盤"

    if market_p[2] > 0.6 and model_p[2] < 0.5:
        return "⚠️ 客隊陷阱盤"

    if abs(model_p[0]-market_p[0]) > 0.15:
        return "⚠️ 異常盤"

    return "正常"

# =========================
# APP
# =========================
st.title("🏦 QUANT HEDGE FUND v3 (GLOBAL)")

raw = fetch_all_odds()

matches = normalize(raw)

if not matches:
    st.warning("⚠️ 使用備援資料")
    matches = normalize(fallback())

st.write("📊 比賽數量:", len(matches))

# 排序（台北時間）
matches = sorted(matches, key=lambda x: x["time"])

for m in matches:

    mp = market_prob(m["odds"])
    adj = adjust(mp)
    sim = simulate(adj)

    evs = [
        ev(sim[0], m["odds"][0]),
        ev(sim[1], m["odds"][1]),
        ev(sim[2], m["odds"][2])
    ]

    pick_i = int(np.argmax(evs))
    pick = ["主隊","平局","客隊"][pick_i]

    st.markdown("----")

    st.markdown(f"### ⚽ {m['away']}（客） vs {m['home']}（主）")

    st.write("🕒 台北時間:", m["time"])

    st.write("📊 市場機率:", [round(x,3) for x in mp])
    st.write("🤖 模型機率:", [round(x,3) for x in sim])

    st.write("💰 EV:", [round(x,3) for x in evs])

    st.write(f"🎯 推薦: {pick}")

    st.write("🚨 盤口分析:", trap(sim, mp))
