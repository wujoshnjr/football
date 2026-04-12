import streamlit as st
import numpy as np
import pandas as pd
import requests
from datetime import datetime

st.set_page_config(page_title="Hedge Fund Execution v21", layout="wide")

# =========================
# 📡 APIs (固定三件套)
# =========================
ODDS_API_KEY = "1ecd27d55ae4f667d16b08d41c00728f"
SPORTMONKS_KEY = "Rd1ZOCcgubiZpmMDSrf2y4DffiiuzFqyrAqRpqqR0AnVCoK2K29iGWQVm9Lm"
NEWS_API_KEY = "aca30b5c29cb379c1d38cc4be8514a64df8d124831e2f07f55714cc2a02ce176"

# =========================
# 💰 INITIAL BANKROLL
# =========================
if "bankroll" not in st.session_state:
    st.session_state.bankroll = 1000

if "trades" not in st.session_state:
    st.session_state.trades = []

# =========================
# 📡 ODDS API
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
# 🧠 AI MODEL (simplified institutional version)
# =========================
def ai_score(team):
    base = abs(hash(team)) % 1000
    form = np.random.uniform(0.4, 0.6)
    injury = np.random.uniform(0.4, 0.6)

    return (base / 2000) * 0.5 + form * 0.3 + (1 - injury) * 0.2

# =========================
# 📊 MARKET PROB
# =========================
def market_prob(odds):
    inv = {k: 1/v for k,v in odds.items()}
    s = sum(inv.values())
    return {k: v/s for k,v in inv.items()}

# =========================
# 💰 EV / KELLY
# =========================
def ev(p, odds):
    return p * odds - 1

def kelly(p, odds):
    b = odds - 1
    return max(0, (b*p - (1-p)) / b)

# =========================
# 💰 EXECUTION ENGINE
# =========================
def execute_trade(pick, odds, p, bankroll):
    k = kelly(p, odds)
    stake = bankroll * min(k, 0.05)

    win = np.random.rand() < p

    pnl = stake * (odds - 1) if win else -stake

    return stake, pnl, win

# =========================
# 📊 METRICS
# =========================
def max_drawdown(equity):
    peak = np.maximum.accumulate(equity)
    drawdown = equity - peak
    return drawdown.min()

def sharpe(returns):
    if len(returns) < 2:
        return 0
    return np.mean(returns) / (np.std(returns) + 1e-9)

# =========================
# 🖥 UI
# =========================
st.title("🏦 Hedge Fund Execution & PnL v21")

if st.button("🚀 RUN EXECUTION DESK"):

    matches = get_matches()
    results = []
    equity = [st.session_state.bankroll]
    returns = []

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
            # PICK
            # =========================
            ev_h = ev(p_home, h_odds)
            ev_a = ev(p_away, a_odds)

            if ev_h > ev_a:
                pick = home
                odds_v = h_odds
                p = p_home
            else:
                pick = away
                odds_v = a_odds
                p = p_away

            # =========================
            # EXECUTION
            # =========================
            bankroll = st.session_state.bankroll

            stake, pnl, win = execute_trade(pick, odds_v, p, bankroll)

            st.session_state.bankroll += pnl

            equity.append(st.session_state.bankroll)
            returns.append(pnl)

            st.session_state.trades.append({
                "Match": f"{home} vs {away}",
                "Pick": pick,
                "Stake": round(stake, 2),
                "PnL": round(pnl, 2),
                "Win": win,
                "Bankroll": round(st.session_state.bankroll, 2)
            })

            results.append({
                "Match": f"{home} vs {away}",
                "Pick": pick,
                "Odds": round(odds_v, 2),
                "Prob": round(p, 3),
                "EV": round(ev(p, odds_v), 3),
                "Stake": round(stake, 2),
                "PnL": round(pnl, 2)
            })

        except:
            continue

    df = pd.DataFrame(results)

    st.success(f"💰 Bankroll: {round(st.session_state.bankroll, 2)}")

    st.dataframe(df, use_container_width=True)

    # =========================
    # 📊 PERFORMANCE
    # =========================
    st.subheader("📊 Performance Metrics")

    st.write({
        "Max Drawdown": round(max_drawdown(np.array(equity)), 2),
        "Sharpe": round(sharpe(returns), 3),
        "Total Trades": len(returns),
        "Win Rate": round(np.mean([t["Win"] for t in st.session_state.trades]), 3)
    })
