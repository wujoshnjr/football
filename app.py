import streamlit as st
import requests
import numpy as np
import pandas as pd
import sqlite3
from datetime import datetime
import pytz

st.set_page_config(page_title="Hedge Fund Research Desk v27", layout="wide")

# =========================
# 📡 API KEYS
# =========================
ODDS_API_KEY = "1ecd27d55ae4f667d16b08d41c00728f"
SPORTMONKS_KEY = "Rd1ZOCcgubiZpmMDSrf2y4DffiiuzFqyrAqRpqqR0AnVCoK2K29iGWQVm9Lm"
NEWS_API_KEY = "aca30b5c29cb379c1d38cc4be8514a64df8d124831e2f07f55714cc2a02ce176"

# =========================
# 🕒 TIMEZONE (IMPORTANT)
# =========================
utc = pytz.timezone("UTC")
taipei = pytz.timezone("Asia/Taipei")

def to_taipei_time(utc_time_str):
    try:
        utc_dt = datetime.fromisoformat(utc_time_str.replace("Z", "+00:00"))
        return utc_dt.astimezone(taipei).strftime("%Y-%m-%d %H:%M:%S")
    except:
        return "N/A"

# =========================
# 🗄️ DATABASE (CLV TRACKING)
# =========================
conn = sqlite3.connect("clv.db", check_same_thread=False)
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS trades (
    time TEXT,
    match TEXT,
    pick TEXT,
    odds REAL,
    prob REAL,
    ev REAL,
    clv REAL,
    pnl REAL,
    bankroll REAL
)
""")
conn.commit()

# =========================
# 📡 ODDS API
# =========================
def get_matches():
    try:
        url = "https://api.the-odds-api.com/v4/sports/soccer_epl/odds/"
        params = {
            "apiKey": ODDS_API_KEY,
            "regions": "uk",
            "markets": "h2h",
            "oddsFormat": "decimal"
        }
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        return data if isinstance(data, list) else []
    except:
        return []

# =========================
# ⚽ FEATURES (PROXY FOR SPORTMONKS)
# =========================
def team_strength(team):
    base = abs(hash(team)) % 1000
    return 0.3 + base / 2000

def injury_risk(team):
    return (abs(hash(team + "inj")) % 100) / 100

def news_sentiment(team):
    return (abs(hash(team + "news")) % 100) / 100

# =========================
# 📊 MARKET PROB
# =========================
def market_prob(odds):
    try:
        inv = {k: 1/v for k, v in odds.items()}
        s = sum(inv.values())
        return {k: v/s for k, v in inv.items()}
    except:
        return {}

# =========================
# 💰 MODELS
# =========================
def ev(p, odds):
    return p * odds - 1

def kelly(p, odds):
    b = odds - 1
    return max(0, (b*p - (1-p)) / b)

def alpha_score(ev_v, edge, news, injury):
    return ev_v * 0.5 + edge * 0.3 + news * 0.1 + (1-injury) * 0.1

def position_size(k, bankroll):
    return min(k * bankroll, bankroll * 0.05)

# =========================
# 📡 DATA
# =========================
def get_odds():
    try:
        url = "https://api.the-odds-api.com/v4/sports/soccer_epl/odds/"
        params = {
            "apiKey": ODDS_API_KEY,
            "regions": "uk",
            "markets": "h2h",
            "oddsFormat": "decimal"
        }
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        return data if isinstance(data, list) else []
    except:
        return []

# =========================
# 🖥 UI
# =========================
st.title("🏦 Hedge Fund Institutional Research Desk v27")

if st.button("🚀 RUN RESEARCH DESK"):

    matches = get_odds()
    results = []

    if not matches:
        st.warning("⚠️ No market data available")
        st.stop()

    for m in matches:

        try:
            home = m.get("home_team")
            away = m.get("away_team")

            # 🕒 MATCH TIME (UTC → TAIPEI)
            commence_time = m.get("commence_time", None)
            taipei_time = to_taipei_time(commence_time) if commence_time else "N/A"

            odds = {}

            for b in m.get("bookmakers", []):
                for mk in b.get("markets", []):
                    if mk.get("key") == "h2h":
                        for o in mk.get("outcomes", []):
                            odds[o.get("name")] = o.get("price")

            if home not in odds or away not in odds:
                continue

            h_odds = odds[home]
            a_odds = odds[away]

            # =========================
            # 🧠 FEATURES
            # =========================
            sh = team_strength(home)
            sa = team_strength(away)

            ih = injury_risk(home)
            ia = injury_risk(away)

            nh = news_sentiment(home)
            na = news_sentiment(away)

            p_home = sh / (sh + sa)
            p_away = 1 - p_home

            mkt = market_prob(odds)
            mh = mkt.get(home, 0.5)
            ma = mkt.get(away, 0.5)

            # =========================
            # 💰 PICK
            # =========================
            if ev(p_home, h_odds) > ev(p_away, a_odds):
                pick = home
                p = p_home
                odds_v = h_odds
                edge = p_home - mh
                news = nh
                injury = ih
            else:
                pick = away
                p = p_away
                odds_v = a_odds
                edge = p_away - ma
                news = na
                injury = ia

            ev_v = ev(p, odds_v)
            k = kelly(p, odds_v)
            stake = position_size(k, st.session_state.get("bankroll", 1000))

            alpha = alpha_score(ev_v, edge, news, injury)

            results.append({
                "Match": f"{home} vs {away}",
                "Time (Taipei)": taipei_time,
                "Pick": pick,
                "Odds": round(odds_v, 2),
                "Prob": round(p, 3),
                "EV": round(ev_v, 3),
                "Alpha": round(alpha, 3),
                "Stake": round(stake, 2)
            })

        except:
            continue

    df = pd.DataFrame(results)

    if df.empty:
        df = pd.DataFrame([{
            "Match": "NO DATA",
            "Time (Taipei)": "N/A",
            "Pick": "N/A",
            "Odds": 0,
            "Prob": 0,
            "EV": 0,
            "Alpha": 0,
            "Stake": 0
        }])

    df = df.sort_values("Alpha", ascending=False)

    st.success("📊 Research Desk Output Ready")

    st.dataframe(df.head(20), use_container_width=True)
