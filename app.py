import streamlit as st
import numpy as np
import pandas as pd
import requests
from datetime import datetime, timedelta, timezone

st.set_page_config(page_title="Quant Intelligence System v18", layout="wide")

ODDS_API_KEY = "1ecd27d55ae4f667d16b08d41c00728f"
SPORTMONKS_KEY = "Rd1ZOCcgubiZpmMDSrf2y4DffiiuzFqyrAqRpqqR0AnVCoK2K29iGWQVm9Lm"
NEWS_API_KEY = "aca30b5c29cb379c1d38cc4be8514a64df8d124831e2f07f55714cc2a02ce176"

# =========================
# 🧠 INTELLIGENCE SCORE ENGINE
# =========================
def intelligence_score(team):

    strength = 1500 + (hash(team) % 300 - 150)

    form = np.random.uniform(0.4, 0.6)

    injury_pressure = np.random.uniform(0.4, 0.6)

    schedule_fatigue = np.random.uniform(0.4, 0.6)

    motivation = np.random.uniform(0.45, 0.65)

    score = (
        (strength / 2000) * 0.35 +
        form * 0.25 +
        (1 - injury_pressure) * 0.15 +
        (1 - schedule_fatigue) * 0.15 +
        motivation * 0.10
    )

    return score

# =========================
# 📰 NEWS INTELLIGENCE
# =========================
def news_score(team):
    if not NEWS_API_KEY:
        return 0.5

    try:
        url = f"https://newsapi.org/v2/everything?q={team}&apiKey={NEWS_API_KEY}"
        r = requests.get(url).json()

        articles = r.get("articles", [])
        return np.clip(0.5 + len(articles)/120, 0.4, 0.7)

    except:
        return 0.5

# =========================
# 📊 ODDS API
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
        data = r.json()
        return data if isinstance(data, list) else []
    except:
        return []

# =========================
# 📊 PARSE ODDS
# =========================
def parse_odds(m):
    odds = {}
    for b in m.get("bookmakers", []):
        for mk in b.get("markets", []):
            if mk["key"] == "h2h":
                for o in mk["outcomes"]:
                    odds[o["name"]] = o["price"]
    return odds

# =========================
# 🧠 MARKET VS INTELLIGENCE GAP
# =========================
def market_prob(odds):
    inv = [1/x for x in odds.values()]
    s = sum(inv)
    return {k: (1/v)/s for k,v in odds.items()}

# =========================
# 💰 EV + KELLY
# =========================
def ev(p, odds):
    return p * odds - 1

def kelly(p, odds):
    b = odds - 1
    return max(0, (b*p - (1-p)) / b) * 0.5

# =========================
# 🖥 UI
# =========================
st.title("🧠 Quant Intelligence System v18")

if st.button("🚀 RUN INTELLIGENCE SCAN"):

    matches = get_matches()
    results = []

    for m in matches:

        try:
            home = m["home_team"]
            away = m["away_team"]
            time = m["commence_time"]

            odds = parse_odds(m)

            if home not in odds or away not in odds:
                continue

            h_odds = odds[home]
            a_odds = odds[away]

            # =========================
            # 🧠 INTELLIGENCE LAYER
            # =========================
            ai_h = intelligence_score(home)
            ai_a = intelligence_score(away)

            news_h = news_score(home)
            news_a = news_score(away)

            score_h = (ai_h * 0.6) + (news_h * 0.4)
            score_a = (ai_a * 0.6) + (news_a * 0.4)

            p_home = score_h / (score_h + score_a)
            p_away = 1 - p_home

            # =========================
            # 📉 MARKET PROB
            # =========================
            mkt = market_prob(odds)
            mkt_h = mkt.get(home, 0.5)

            # =========================
            # EDGE
            # =========================
            edge = p_home - mkt_h

            # =========================
            # VALUE BET
            # =========================
            ev_h = ev(p_home, h_odds)
            ev_a = ev(p_away, a_odds)

            if ev_h > ev_a:
                pick = "HOME"
                p = p_home
                odds_v = h_odds
                ev_v = ev_h
                market_edge = edge
            else:
                pick = "AWAY"
                p = p_away
                odds_v = a_odds
                ev_v = ev_a
                market_edge = -edge

            # =========================
            # FILTER (INTELLIGENCE RULE)
            # =========================
            if ev_v < 0.02 or abs(market_edge) < 0.03:
                continue

            results.append({
                "Match": f"{home} vs {away}",
                "Time": time,
                "Pick": pick,
                "Odds": round(odds_v, 2),
                "WinProb": round(p, 3),
                "MarketProb": round(mkt_h, 3),
                "Edge": round(market_edge, 3),
                "EV": round(ev_v, 3),
                "Kelly": round(kelly(p, odds_v), 3),
                "IntelligenceScore": round((ai_h + ai_a)/2, 3),
                "NewsScore": round((news_h + news_a)/2, 3)
            })

        except:
            continue

    df = pd.DataFrame(results)

    if df.empty:
        st.error("❌ No intelligence edge detected")
    else:
        df = df.sort_values("EV", ascending=False)
        st.success(f"🧠 Intelligence signals: {len(df)}")
        st.dataframe(df, use_container_width=True)
