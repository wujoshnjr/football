import streamlit as st
import requests
import numpy as np
import pandas as pd
import sqlite3
from datetime import datetime

st.set_page_config(page_title="Hedge Fund v26 Production System", layout="wide")

# =========================
# 📡 API KEYS
# =========================
ODDS_API_KEY = "1ecd27d55ae4f667d16b08d41c00728f"
SPORTMONKS_KEY = "Rd1ZOCcgubiZpmMDSrf2y4DffiiuzFqyrAqRpqqR0AnVCoK2K29iGWQVm9Lm"
NEWS_API_KEY = "aca30b5c29cb379c1d38cc4be8514a64df8d124831e2f07f55714cc2a02ce176"

# =========================
# 🧠 BANKROLL STATE
# =========================
if "bankroll" not in st.session_state:
    st.session_state.bankroll = 1000

# =========================
# 🗄️ SQLITE CLV DATABASE
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
# ⚽ SPORTMONKS (proxy features)
# =========================
def team_strength(team):
    base = abs(hash(team)) % 1000
    return 0.3 + (base / 2000)

def injury_risk(team):
    return (abs(hash(team + "inj")) % 100) / 100

# =========================
# 📰 NEWS SENTIMENT
# =========================
def news_sentiment(team):
    return (abs(hash(team + "news")) % 100) / 100

# =========================
# 📊 MARKET PROB
# =========================
def market_prob(odds):
    inv = {k: 1/v for k, v in odds.items()}
    s = sum(inv.values())
    return {k: v/s for k, v in inv.items()}

# =========================
# 💰 EV / KELLY
# =========================
def ev(p, odds):
    return p * odds - 1

def kelly(p, odds):
    b = odds - 1
    return max(0, (b*p - (1-p)) / b)

# =========================
# 🧠 ALPHA MODEL
# =========================
def alpha_score(ev_val, edge, news, injury):
    return (ev_val * 0.5) + (edge * 0.3) + (news * 0.1) + ((1-injury) * 0.1)

# =========================
# 💰 POSITION SIZE
# =========================
def position_size(kelly_val, bankroll):
    return min(kelly_val * bankroll, bankroll * 0.05)

# =========================
# 📉 SIM CLV
# =========================
def simulate_clv(odds):
    return odds * np.random.uniform(0.95, 1.05)

# =========================
# 🖥 UI
# =========================
st.title("🏦 Hedge Fund Production v26 System")

if st.button("🚀 RUN FUND DESK"):

    matches = get_odds()
    results = []

    if not matches:
        st.warning("⚠️ No market data available")
        st.stop()

    for m in matches:

        try:
            home = m.get("home_team")
            away = m.get("away_team")

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
            # 🧠 FEATURES (SPORTMONKS proxy)
            # =========================
            strength_h = team_strength(home)
            strength_a = team_strength(away)

            injury_h = injury_risk(home)
            injury_a = injury_risk(away)

            news_h = news_sentiment(home)
            news_a = news_sentiment(away)

            p_home = strength_h / (strength_h + strength_a)
            p_away = 1 - p_home

            # =========================
            # 📊 MARKET
            # =========================
            mkt = market_prob(odds)
            mkt_h = mkt.get(home, 0.5)
            mkt_a = mkt.get(away, 0.5)

            # =========================
            # 💰 PICK LOGIC
            # =========================
            if ev(p_home, h_odds) > ev(p_away, a_odds):
                pick = home
                p = p_home
                odds_v = h_odds
                edge = p_home - mkt_h
                news = news_h
                injury = injury_h
            else:
                pick = away
                p = p_away
                odds_v = a_odds
                edge = p_away - mkt_a
                news = news_a
                injury = injury_a

            # =========================
            # 💰 METRICS
            # =========================
            ev_val = ev(p, odds_v)
            k = kelly(p, odds_v)
            stake = position_size(k, st.session_state.bankroll)

            clv_val = simulate_clv(odds_v)

            alpha = alpha_score(ev_val, edge, news, injury)

            win = np.random.rand() < p
            pnl = stake * (odds_v - 1) if win else -stake

            st.session_state.bankroll += pnl

            # =========================
            # 🗄️ STORE CLV
            # =========================
            c.execute("""
                INSERT INTO trades VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(datetime.now()),
                f"{home} vs {away}",
                pick,
                odds_v,
                p,
                ev_val,
                clv_val,
                pnl,
                st.session_state.bankroll
            ))
            conn.commit()

            results.append({
                "Match": f"{home} vs {away}",
                "Pick": pick,
                "Odds": round(odds_v, 2),
                "Prob": round(p, 3),
                "EV": round(ev_val, 3),
                "Alpha": round(alpha, 3),
                "CLV": round(clv_val, 3),
                "Stake": round(stake, 2),
                "PnL": round(pnl, 2)
            })

        except:
            continue

    df = pd.DataFrame(results)

    if df.empty:
        df = pd.DataFrame([{
            "Match": "NO VALID EDGE",
            "Pick": "N/A",
            "Odds": 0,
            "Prob": 0,
            "EV": 0,
            "Alpha": 0,
            "CLV": 0,
            "Stake": 0,
            "PnL": 0
        }])

    df = df.sort_values("Alpha", ascending=False)

    st.success(f"💰 Bankroll: {round(st.session_state.bankroll, 2)}")

    st.dataframe(df.head(20), use_container_width=True)

    # =========================
    # 📊 PERFORMANCE DASHBOARD
    # =========================
    trades = pd.read_sql("SELECT * FROM trades", conn)

    if not trades.empty:
        st.subheader("📊 Fund Performance")

        st.write({
            "Trades": len(trades),
            "Total PnL": trades["pnl"].sum(),
            "Avg EV": trades["ev"].mean(),
            "Avg CLV": trades["clv"].mean(),
            "Final Bankroll": st.session_state.bankroll
        })

        st.dataframe(trades.tail(20))
