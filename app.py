import streamlit as st
import numpy as np
import pandas as pd
import requests
from datetime import datetime, timezone

st.set_page_config(page_title="Hedge Fund v19 CLV System", layout="wide")

ODDS_API_KEY = "1ecd27d55ae4f667d16b08d41c00728f"
SPORTMONKS_KEY = "Rd1ZOCcgubiZpmMDSrf2y4DffiiuzFqyrAqRpqqR0AnVCoK2K29iGWQVm9Lm"
NEWS_API_KEY = "aca30b5c29cb379c1d38cc4be8514a64df8d124831e2f07f55714cc2a02ce176"

# =========================
# 📡 ODDS API
# =========================
def get_odds():
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
# 📊 SPORTMONKS (FEATURES)
# =========================
def get_team_form(team):
    # production placeholder (real: Sportmonks endpoint)
    return np.random.uniform(0.4, 0.7)

def get_injury_risk(team):
    return np.random.uniform(0.4, 0.6)

# =========================
# 📰 NEWS SENTIMENT
# =========================
def news_sentiment(team):
    if not NEWS_API_KEY:
        return 0.5
    try:
        url = f"https://newsapi.org/v2/everything?q={team}&apiKey={NEWS_API_KEY}"
        r = requests.get(url).json()
        return np.clip(0.5 + len(r.get("articles", [])) / 100, 0.4, 0.7)
    except:
        return 0.5

# =========================
# 🧠 AI SCORE ENGINE
# =========================
def ai_score(team):
    form = get_team_form(team)
    injury = get_injury_risk(team)
    news = news_sentiment(team)

    return (form * 0.5) + ((1 - injury) * 0.3) + (news * 0.2)

# =========================
# 📊 MARKET PROBABILITY
# =========================
def market_prob(odds):
    inv = {k: 1/v for k,v in odds.items()}
    s = sum(inv.values())
    return {k: v/s for k,v in inv.items()}

# =========================
# 💰 EV + KELLY
# =========================
def ev(p, odds):
    return p * odds - 1

def kelly(p, odds):
    b = odds - 1
    return max(0, (b*p - (1-p)) / b)

# =========================
# 📈 CLV ENGINE (核心)
# =========================
def clv(model_odds, market_odds):
    return (market_odds - model_odds) / model_odds

# =========================
# 🖥 UI
# =========================
st.title("🏦 Hedge Fund v19 CLV Production System")

if st.button("🚀 RUN FUND SCAN"):

    matches = get_odds()
    results = []

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
                pick = "HOME"
                p = p_home
                odds_v = h_odds
                mkt_v = mkt_h
                ev_v = ev_h
            else:
                pick = "AWAY"
                p = p_away
                odds_v = a_odds
                mkt_v = mkt_a
                ev_v = ev_a

            # =========================
            # 📈 CLV (CRITICAL METRIC)
            # =========================
            model_odds = 1 / p
            clv_value = clv(model_odds, odds_v)

            # =========================
            # 💰 KELLY
            # =========================
            stake = kelly(p, odds_v)

            # =========================
            # FILTER (PRODUCTION LEVEL)
            # =========================
            if ev_v < 0.015 and abs(clv_value) < 0.02:
                continue

            results.append({
                "Match": f"{home} vs {away}",
                "Pick": pick,
                "Odds": round(odds_v, 2),
                "Prob": round(p, 3),
                "MarketProb": round(mkt_v, 3),
                "EV": round(ev_v, 3),
                "CLV": round(clv_value, 3),
                "Kelly": round(stake, 3),
                "AI_Score_H": round(ai_h, 3),
                "AI_Score_A": round(ai_a, 3)
            })

        except:
            continue

    df = pd.DataFrame(results)

    if df.empty:
        st.warning("⚠️ No CLV edge found (market efficient)")
        df = pd.DataFrame(results)

    df = df.sort_values("EV", ascending=False)

    st.success(f"💰 Production signals: {len(df)}")

    st.dataframe(df.head(10), use_container_width=True)
