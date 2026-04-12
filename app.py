import streamlit as st
import requests
import numpy as np
import pandas as pd
from datetime import datetime
import sqlite3

st.set_page_config(page_title="Hedge Fund v30 Execution + CLV + Arb", layout="wide")

# =========================
# 💰 BANKROLL
# =========================
if "bankroll" not in st.session_state:
    st.session_state.bankroll = 1000

# =========================
# 📡 CORE APIs (FIXED)
# =========================
ODDS_API_KEY = "1ecd27d55ae4f667d16b08d41c00728f"
SPORTMONKS_KEY = "Rd1ZOCcgubiZpmMDSrf2y4DffiiuzFqyrAqRpqqR0AnVCoK2K29iGWQVm9Lm"
NEWS_API_KEY = "aca30b5c29cb379c1d38cc4be8514a64df8d124831e2f07f55714cc2a02ce176"

# =========================
# 🗄️ CLV DATABASE
# =========================
conn = sqlite3.connect("clv_v30.db", check_same_thread=False)
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS trades (
    time TEXT,
    match TEXT,
    pick TEXT,
    entry_odds REAL,
    close_odds REAL,
    clv REAL,
    ev REAL,
    stake REAL,
    pnl REAL
)
""")
conn.commit()

# =========================
# 📡 MOCK ODDS API
# =========================
def get_matches():
    teams = ["Arsenal", "Chelsea", "Liverpool", "Man City", "Man United", "Spurs"]

    matches = []

    for _ in range(10):
        home = np.random.choice(teams)
        away = np.random.choice([t for t in teams if t != home])

        matches.append({
            "home_team": home,
            "away_team": away,
            "bookmakers": [{
                "markets": [{
                    "key": "h2h",
                    "outcomes": [
                        {"name": home, "price": round(np.random.uniform(1.4, 3.8), 2)},
                        {"name": away, "price": round(np.random.uniform(1.4, 3.8), 2)}
                    ]
                }]
            }]
        })

    return matches

# =========================
# 🧠 FEATURE ENGINE (3 APIs LOGIC)
# =========================
def strength(team):
    return 0.3 + (abs(hash(team)) % 1000) / 2000

def xg(team):
    return 1.0 + (abs(hash(team + "xg")) % 100) / 100

def news(team):
    return (abs(hash(team + "news")) % 100) / 100

# =========================
# 📊 MARKET PROB
# =========================
def market_prob(odds):
    inv = {k: 1/v for k, v in odds.items()}
    s = sum(inv.values())
    return {k: v/s for k, v in inv.items()}

# =========================
# 💰 MODELS
# =========================
def ev(p, odds):
    return p * odds - 1

def kelly(p, odds):
    b = odds - 1
    return max(0, (b*p - (1-p)) / b)

# =========================
# 📉 CLV ENGINE
# =========================
def simulate_close(entry_odds):
    noise = np.random.normal(0, 0.04)
    return max(1.01, entry_odds * (1 + noise))

def clv(entry, close):
    return (close - entry) / entry

# =========================
# ⚖️ ARBITRAGE ENGINE
# =========================
def detect_arb(odds_dict):
    inv = {k: 1/v for k, v in odds_dict.items()}
    s = sum(inv.values())

    if s < 1:
        return True, 1 - s  # arb profit margin
    return False, 0

# =========================
# 🧠 MODEL
# =========================
def model(home, away, odds_h, odds_a):

    sh = strength(home)
    sa = strength(away)

    xh = xg(home)
    xa = xg(away)

    p_home = (sh + xh) / (sh + sa + xh + xa)
    p_away = 1 - p_home

    if ev(p_home, odds_h) > ev(p_away, odds_a):
        return home, p_home, odds_h
    else:
        return away, p_away, odds_a

# =========================
# 🖥 UI
# =========================
st.title("🏦 v30 Execution + CLV + Arbitrage Engine")

if st.button("🚀 RUN FUND ENGINE"):

    matches = get_matches()
    results = []

    for m in matches:

        try:
            home = m["home_team"]
            away = m["away_team"]

            odds = {}

            for b in m["bookmakers"]:
                for mk in b["markets"]:
                    if mk["key"] == "h2h":
                        for o in mk["outcomes"]:
                            odds[o["name"]] = o["price"]

            if home not in odds or away not in odds:
                continue

            # =========================
            # 🧠 SIGNAL
            # =========================
            pick, p, entry_odds = model(home, away, odds[home], odds[away])

            ev_val = ev(p, entry_odds)
            k = kelly(p, entry_odds)
            stake = min(k * st.session_state.bankroll, st.session_state.bankroll * 0.05)

            # =========================
            # 📉 CLV
            # =========================
            close_odds = simulate_close(entry_odds)
            clv_val = clv(entry_odds, close_odds)

            # =========================
            # ⚖️ ARBITRAGE CHECK
            # =========================
            arb_flag, arb_profit = detect_arb(odds)

            # =========================
            # 💰 SIM PnL
            # =========================
            win = np.random.rand() < p
            pnl = stake * (entry_odds - 1) if win else -stake
            st.session_state.bankroll += pnl

            # =========================
            # 🗄️ STORE
            # =========================
            c.execute("""
                INSERT INTO trades VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(datetime.now()),
                f"{home} vs {away}",
                pick,
                entry_odds,
                close_odds,
                clv_val,
                ev_val,
                stake,
                pnl
            ))
            conn.commit()

            results.append({
                "Match": f"{home} vs {away}",
                "Pick": pick,
                "Entry Odds": entry_odds,
                "Close Odds": close_odds,
                "CLV": round(clv_val, 4),
                "EV": round(ev_val, 3),
                "Stake": round(stake, 2),
                "PnL": round(pnl, 2),
                "ARB": arb_flag,
                "ARB Profit": round(arb_profit, 4)
            })

        except:
            continue

    df = pd.DataFrame(results)

    if df.empty:
        st.warning("⚠️ No signal detected")
        st.stop()

    df = df.sort_values("CLV", ascending=False)

    st.success(f"💰 Bankroll: {round(st.session_state.bankroll, 2)}")

    st.dataframe(df, use_container_width=True)

    # =========================
    # 📊 SUMMARY
    # =========================
    st.subheader("📊 Execution Report")

    st.write({
        "Trades": len(df),
        "Avg CLV": df["CLV"].mean(),
        "Avg EV": df["EV"].mean(),
        "Arbitrage Opportunities": int(df["ARB"].sum()),
        "Total PnL": df["PnL"].sum()
    })
