import streamlit as st
import numpy as np
import pandas as pd
import requests
from datetime import datetime

st.set_page_config(page_title="Hedge Fund Institutional v22", layout="wide")

# =========================
# 🧠 API KEYS (固定三件套)
# =========================
ODDS_API_KEY = "1ecd27d55ae4f667d16b08d41c00728f"
SPORTMONKS_KEY = "Rd1ZOCcgubiZpmMDSrf2y4DffiiuzFqyrAqRpqqR0AnVCoK2K29iGWQVm9Lm"
NEWS_API_KEY = "aca30b5c29cb379c1d38cc4be8514a64df8d124831e2f07f55714cc2a02ce176"

# =========================
# 💰 SESSION STATE (PORTFOLIO)
# =========================
if "bankroll" not in st.session_state:
    st.session_state.bankroll = 1000

if "clv_db" not in st.session_state:
    st.session_state.clv_db = []

# =========================
# 📡 ODDS DATA
# =========================
def get_matches():
    url = "https://api.the-odds-api.com/v4/sports/soccer/odds/"
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": "uk",
        "markets": "h2h",
        "oddsFormat": "decimal"
    }
    try:
        r = requests.get(url, timeout=10)
        return r.json() if isinstance(r.json(), list) else []
    except:
        return []

# =========================
# 📊 MARKET PROB
# =========================
def market_prob(odds):
    inv = {k: 1/v for k, v in odds.items()}
    s = sum(inv.values())
    return {k: v/s for k, v in inv.items()}

# =========================
# 🧠 AI SCORE (institutional proxy)
# =========================
def ai_score(team):
    base = abs(hash(team)) % 1000
    form = np.random.uniform(0.4, 0.6)
    injury = np.random.uniform(0.4, 0.6)
    return (base / 2000) * 0.5 + form * 0.3 + (1 - injury) * 0.2

# =========================
# 💰 EV / KELLY
# =========================
def ev(p, odds):
    return p * odds - 1

def kelly(p, odds):
    b = odds - 1
    return max(0, (b*p - (1-p)) / b)

# =========================
# 📉 CLV ENGINE
# =========================
def clv(entry, close):
    return (close - entry) / entry

# =========================
# 📊 MULTI-MARKET SCORE
# =========================
def market_score(ev_v, clv_v, edge):
    return (ev_v * 0.5) + (abs(clv_v) * 0.3) + (abs(edge) * 0.2)

# =========================
# 💰 PORTFOLIO LIMIT
# =========================
def position_size(kelly_val, bankroll):
    return min(kelly_val * bankroll, bankroll * 0.05)

# =========================
# 🖥 UI
# =========================
st.title("🏦 Hedge Fund Institutional System v22")

if st.button("🚀 RUN INSTITUTIONAL SCAN"):

    matches = get_matches()
    results = []

    bankroll = st.session_state.bankroll

    for m in matches:

        try:
            home = m["home_team"]
            away = m["away_team"]

            odds = {}
            for b in m.get("bookmakers", []):
                for mk in b.get("markets", []):
                    if mk["key"] == "h2h":
                        for o in mk["outcomes"]:
                            odds[o["name"]] = o["price"]

            if home not in odds or away not in odds:
                continue

            h_odds = odds[home]
            a_odds = odds[away]

            # =========================
            # 🧠 MODEL
            # =========================
            ai_h = ai_score(home)
            ai_a = ai_score(away)

            p_home = ai_h / (ai_h + ai_a)
            p_away = 1 - p_home

            # =========================
            # 📉 MARKET
            # =========================
            mkt = market_prob(odds)
            mkt_h = mkt.get(home, 0.5)
            mkt_a = mkt.get(away, 0.5)

            # =========================
            # 💰 VALUE
            # =========================
            ev_h = ev(p_home, h_odds)
            ev_a = ev(p_away, a_odds)

            if ev_h > ev_a:
                pick = home
                p = p_home
                odds_v = h_odds
                ev_v = ev_h
                mkt_v = mkt_h
                edge = p_home - mkt_h
            else:
                pick = away
                p = p_away
                odds_v = a_odds
                ev_v = ev_a
                mkt_v = mkt_a
                edge = p_away - mkt_a

            # =========================
            # 📉 SIMULATED EXECUTION
            # =========================
            entry_odds = odds_v
            close_odds = entry_odds * np.random.uniform(0.95, 1.05)
            clv_v = clv(entry_odds, close_odds)

            # =========================
            # 💰 POSITION SIZING
            # =========================
            k = kelly(p, odds_v)
            stake = position_size(k, bankroll)

            # =========================
            # 📊 INSTITUTIONAL SCORE
            # =========================
            score = market_score(ev_v, clv_v, edge)

            # =========================
            # 📊 UPDATE BANKROLL (SIMULATION)
            # =========================
            win = np.random.rand() < p

            pnl = stake * (odds_v - 1) if win else -stake
            st.session_state.bankroll += pnl

            # =========================
            # 📊 STORE CLV DATABASE
            # =========================
            st.session_state.clv_db.append({
                "Match": f"{home} vs {away}",
                "Pick": pick,
                "EV": ev_v,
                "CLV": clv_v,
                "Stake": stake,
                "PnL": pnl,
                "Bankroll": st.session_state.bankroll
            })

            results.append({
                "Match": f"{home} vs {away}",
                "Pick": pick,
                "Odds": round(odds_v, 2),
                "Prob": round(p, 3),
                "MarketProb": round(mkt_v, 3),
                "EV": round(ev_v, 3),
                "Edge": round(edge, 3),
                "CLV": round(clv_v, 3),
                "Stake": round(stake, 2),
                "Score": round(score, 3),
                "PnL": round(pnl, 2)
            })

        except:
            continue

    df = pd.DataFrame(results)

    df = df.sort_values("Score", ascending=False)

    st.success(f"💰 Bankroll: {round(st.session_state.bankroll, 2)}")

    st.dataframe(df.head(15), use_container_width=True)

    # =========================
    # 📊 PERFORMANCE DASHBOARD
    # =========================
    st.subheader("📊 Institutional Performance Dashboard")

    clv_df = pd.DataFrame(st.session_state.clv_db)

    if not clv_df.empty:
        st.write({
            "Total Trades": len(clv_df),
            "Avg EV": clv_df["EV"].mean(),
            "Avg CLV": clv_df["CLV"].mean(),
            "Total PnL": clv_df["PnL"].sum(),
            "Final Bankroll": st.session_state.bankroll
        })

        st.dataframe(clv_df.tail(20), use_container_width=True)
