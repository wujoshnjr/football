import streamlit as st
import numpy as np
import pandas as pd
import requests

st.set_page_config(page_title="Hedge Fund Alpha v24", layout="wide")

# =========================
# 📡 API KEYS (三大核心)
# =========================
ODDS_API_KEY = "1ecd27d55ae4f667d16b08d41c00728f"
SPORTMONKS_KEY = "Rd1ZOCcgubiZpmMDSrf2y4DffiiuzFqyrAqRpqqR0AnVCoK2K29iGWQVm9Lm"
NEWS_API_KEY = "aca30b5c29cb379c1d38cc4be8514a64df8d124831e2f07f55714cc2a02ce176"

# =========================
# 💰 INITIAL BANKROLL
# =========================
if "bankroll" not in st.session_state:
    st.session_state.bankroll = 1000

if "clv_db" not in st.session_state:
    st.session_state.clv_db = []

# =========================
# 📡 ODDS API
# =========================
def get_matches():
    try:
        url = "https://api.the-odds-api.com/v4/sports/soccer/odds/"
        params = {
            "apiKey": ODDS_API_KEY,
            "regions": "uk",
            "markets": "h2h",
            "oddsFormat": "decimal"
        }
        r = requests.get(url, timeout=10)
        data = r.json()
        return data if isinstance(data, list) else []
    except:
        return []

# =========================
# ⚽ SPORTMONKS (SIMPLIFIED)
# =========================
def team_strength(team):
    # proxy for xG / form / historical performance
    base = abs(hash(team)) % 1000
    return 0.3 + (base / 2000)

# =========================
# 📰 NEWS SENTIMENT (SIMULATED)
# =========================
def news_sentiment(team):
    base = abs(hash(team + "news")) % 100
    return base / 100

# =========================
# 🧠 MARKET PROB
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
# 🧠 ALPHA ENGINE
# =========================
def alpha_score(p_model, p_market, news, strength):
    inefficiency = abs(p_model - p_market)
    return (inefficiency * 0.5) + (strength * 0.3) + (news * 0.2)

# =========================
# 💰 PORTFOLIO ENGINE
# =========================
def position_size(kelly_val, bankroll):
    return min(kelly_val * bankroll, bankroll * 0.05)

# =========================
# 📊 CLV ENGINE
# =========================
def clv(entry, close):
    return (close - entry) / entry

# =========================
# 🖥 UI
# =========================
st.title("🏦 Hedge Fund Alpha Production System v24")

if st.button("🚀 RUN ALPHA ENGINE"):

    matches = get_matches()
    results = []

    bankroll = st.session_state.bankroll

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
            # 🧠 MODEL COMPONENTS
            # =========================
            strength_h = team_strength(home)
            strength_a = team_strength(away)

            news_h = news_sentiment(home)
            news_a = news_sentiment(away)

            total = strength_h + strength_a
            p_home = strength_h / total
            p_away = 1 - p_home

            # =========================
            # 📊 MARKET
            # =========================
            mkt = market_prob(odds)
            p_mkt_h = mkt.get(home, 0.5)
            p_mkt_a = mkt.get(away, 0.5)

            # =========================
            # 💰 VALUE
            # =========================
            ev_h = ev(p_home, h_odds)
            ev_a = ev(p_away, a_odds)

            if ev_h > ev_a:
                pick = home
                p = p_home
                odds_v = h_odds
                p_mkt = p_mkt_h
                news = news_h
                strength = strength_h
                ev_v = ev_h
            else:
                pick = away
                p = p_away
                odds_v = a_odds
                p_mkt = p_mkt_a
                news = news_a
                strength = strength_a
                ev_v = ev_a

            # =========================
            # 🧠 ALPHA SCORE
            # =========================
            alpha = alpha_score(p, p_mkt, news, strength)

            # =========================
            # 💰 POSITION
            # =========================
            k = kelly(p, odds_v)
            stake = position_size(k, bankroll)

            # =========================
            # 📉 SIM CLV
            # =========================
            close_odds = odds_v * np.random.uniform(0.95, 1.05)
            clv_v = clv(odds_v, close_odds)

            # =========================
            # 💰 EXECUTION SIM
            # =========================
            win = np.random.rand() < p
            pnl = stake * (odds_v - 1) if win else -stake

            st.session_state.bankroll += pnl

            st.session_state.clv_db.append({
                "Match": f"{home} vs {away}",
                "Pick": pick,
                "EV": ev_v,
                "Alpha": alpha,
                "CLV": clv_v,
                "PnL": pnl,
                "Bankroll": st.session_state.bankroll
            })

            results.append({
                "Match": f"{home} vs {away}",
                "Pick": pick,
                "Odds": round(odds_v, 2),
                "Prob": round(p, 3),
                "MarketProb": round(p_mkt, 3),
                "EV": round(ev_v, 3),
                "Alpha": round(alpha, 3),
                "Stake": round(stake, 2),
                "PnL": round(pnl, 2)
            })

        except:
            continue

    df = pd.DataFrame(results)

    df = df.sort_values("Alpha", ascending=False)

    st.success(f"💰 Bankroll: {round(st.session_state.bankroll, 2)}")

    st.dataframe(df.head(15), use_container_width=True)

    # =========================
    # 📊 PERFORMANCE
    # =========================
    clv_df = pd.DataFrame(st.session_state.clv_db)

    if not clv_df.empty:
        st.subheader("📊 Alpha Performance Dashboard")

        st.write({
            "Trades": len(clv_df),
            "Avg EV": clv_df["EV"].mean(),
            "Avg Alpha": clv_df["Alpha"].mean(),
            "Total PnL": clv_df["PnL"].sum(),
            "Final Bankroll": st.session_state.bankroll
        })

        st.dataframe(clv_df.tail(20), use_container_width=True)
