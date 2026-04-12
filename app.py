import streamlit as st
import numpy as np
import pandas as pd
import requests
from datetime import datetime, timedelta, timezone

st.set_page_config(page_title="Xu Football Model v14 Institutional Pro", layout="wide")

# =========================
# 🔑 API KEYS
# =========================
ODDS_API_KEY = "1ecd27d55ae4f667d16b08d41c00728f"
SPORTMONKS_KEY = "Rd1ZOCcgubiZpmMDSrf2y4DffiiuzFqyrAqRpqqR0AnVCoK2K29iGWQVm9Lm"
NEWS_API_KEY = "aca30b5c29cb379c1d38cc4be8514a64df8d124831e2f07f55714cc2a02ce176"

# =========================
# 🧪 API HEALTH CHECK
# =========================
def api_ok(key):
    return key and "YOUR_" not in key

odds_ok = api_ok(ODDS_API_KEY)
sport_ok = api_ok(SPORTMONKS_KEY)
news_ok = api_ok(NEWS_API_KEY)

# =========================
# 🕒 24H FILTER
# =========================
def within_24h(t):
    try:
        dt = datetime.fromisoformat(t.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        return now <= dt <= now + timedelta(hours=24)
    except:
        return False

# =========================
# 📡 ODDS API
# =========================
def get_matches():
    if not odds_ok:
        return []

    url = "https://api.the-odds-api.com/v4/sports/soccer/odds/"
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": "uk",
        "markets": "h2h",
        "oddsFormat": "decimal"
    }

    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        return [m for m in data if within_24h(m.get("commence_time", ""))]
    except:
        return []

# =========================
# 📊 FORM (Sportmonks safe)
# =========================
def get_form(team):
    if not sport_ok:
        return 0.5

    try:
        url = f"https://api.sportmonks.com/v3/football/teams/search/{team}?api_token={SPORTMONKS_KEY}"
        r = requests.get(url).json()

        if not r.get("data"):
            return 0.5

        team_id = r["data"][0]["id"]

        url2 = f"https://api.sportmonks.com/v3/football/teams/{team_id}?api_token={SPORTMONKS_KEY}&include=latest"
        r2 = requests.get(url2).json()

        matches = r2.get("data", {}).get("latest", [])

        w = 0
        t = 0

        for m in matches:
            try:
                s = m["scores"]
                if len(s) < 2:
                    continue

                hg = s[0]["score"]["goals"]
                ag = s[1]["score"]["goals"]

                t += 1
                if hg > ag:
                    w += 1
            except:
                continue

        return w / t if t else 0.5

    except:
        return 0.5

# =========================
# 📰 NEWS SENTIMENT
# =========================
def news_sentiment(team):
    if not news_ok:
        return 0.5

    try:
        url = f"https://newsapi.org/v2/everything?q={team}&apiKey={NEWS_API_KEY}"
        r = requests.get(url).json()

        articles = r.get("articles", [])
        if not articles:
            return 0.5

        # simplified sentiment proxy
        return np.clip(0.5 + len(articles)/100, 0.4, 0.7)

    except:
        return 0.5

# =========================
# 📊 ODDS PARSER
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
# 🧠 MODEL (institutional fusion)
# =========================
def elo(team):
    return 1500 + (hash(team) % 300 - 150)

def elo_p(a, b):
    return 1 / (1 + 10 ** ((b - a) / 400))

def ev(p, odds):
    return p * odds - 1

def kelly(p, odds):
    b = odds - 1
    return max(0, (b*p - (1-p)) / b) * 0.5

# =========================
# 🖥 UI
# =========================
st.title("⚽ Xu Football Model v14 Institutional Pro")

st.info(f"""
API STATUS:
- Odds API: {"OK" if odds_ok else "MISSING"}
- Sportmonks: {"OK" if sport_ok else "MISSING"}
- News API: {"OK" if news_ok else "MISSING"}
""")

if st.button("🚀 RUN INSTITUTIONAL SCAN"):

    matches = get_matches()
    results = []

    for m in matches:
        try:
            home = m["home_team"]
            away = m["away_team"]
            time = m["commence_time"]

            odds = parse_odds(m)
            h_odds = odds.get(home, 2.0)
            a_odds = odds.get(away, 2.0)

            # =========================
            # DATA LAYERS
            # =========================
            form_h = get_form(home)
            form_a = get_form(away)

            news_h = news_sentiment(home)
            news_a = news_sentiment(away)

            elo_prob = elo_p(elo(home), elo(away))

            # =========================
            # CONFIDENCE SCORE
            # =========================
            data_quality = (
                (1 if odds_ok else 0) +
                (1 if sport_ok else 0) +
                (1 if news_ok else 0)
            ) / 3

            # =========================
            # FINAL PROBABILITY
            # =========================
            p_home = (
                elo_prob * 0.4 +
                form_h * 0.25 +
                news_h * 0.15 +
                0.5 * 0.2
            )

            p_away = 1 - p_home

            ev_h = ev(p_home, h_odds)
            ev_a = ev(p_away, a_odds)

            if ev_h > ev_a:
                pick = "HOME"
                p = p_home
                odds_v = h_odds
                ev_v = ev_h
            else:
                pick = "AWAY"
                p = p_away
                odds_v = a_odds
                ev_v = ev_a

            # =========================
            # FILTER (institutional)
            # =========================
            if ev_v < 0.03 or data_quality < 0.5:
                continue

            results.append({
                "Match": f"{home} vs {away}",
                "Time": time,
                "Pick": pick,
                "Odds": round(odds_v, 2),
                "WinProb": round(p, 3),
                "EV": round(ev_v, 3),
                "Kelly": round(kelly(p, odds_v), 3),
                "Form": round((form_h + form_a)/2, 2),
                "News": round((news_h + news_a)/2, 2),
                "DataQuality": round(data_quality, 2)
            })

        except:
            continue

    df = pd.DataFrame(results)

    if df.empty:
        st.error("❌ No institutional-grade opportunities found")
    else:
        df = df.sort_values("EV", ascending=False)
        st.success(f"✅ Institutional signals: {len(df)}")
        st.dataframe(df, use_container_width=True)
