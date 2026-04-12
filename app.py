import streamlit as st
import numpy as np
import pandas as pd
import requests
from datetime import datetime, timedelta, timezone

st.set_page_config(page_title="Xu Football Model v10", layout="wide")

ODDS_API_KEY = "1ecd27d55ae4f667d16b08d41c00728f"
SPORTMONKS_KEY = "Rd1ZOCcgubiZpmMDSrf2y4DffiiuzFqyrAqRpqqR0AnVCoK2K29iGWQVm9Lm"

# ======================
# 🕒 Filter 24h matches
# ======================
def is_within_24h(commence_time):
    try:
        match_time = datetime.fromisoformat(commence_time.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        return now <= match_time <= now + timedelta(hours=24)
    except:
        return False

# ======================
# 📡 Odds API
# ======================
def get_matches():
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
        if not isinstance(data, list):
            return []
        return [m for m in data if is_within_24h(m.get("commence_time", ""))]
    except:
        return []

# ======================
# 📊 Parse Odds
# ======================
def parse_odds(match):
    odds = {}
    for b in match.get("bookmakers", []):
        for m in b.get("markets", []):
            for o in m.get("outcomes", []):
                odds[o["name"]] = o["price"]
    return odds

# ======================
# 📊 Team Form (Sportmonks)
# ======================
def get_team_form(team):
    if not SPORTMONKS_KEY:
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

        wins = 0
        total = 0

        for m in matches:
            try:
                scores = m["scores"]
                hg = scores[0]["score"]["goals"]
                ag = scores[1]["score"]["goals"]

                total += 1
                if hg > ag:
                    wins += 1
            except:
                continue

        return wins / total if total else 0.5

    except:
        return 0.5

# ======================
# 📊 H2H (fallback)
# ======================
def get_h2h():
    return 0.5

# ======================
# 📊 Elo
# ======================
def elo(team):
    return 1500 + (hash(team) % 300 - 150)

def elo_prob(a, b):
    return 1 / (1 + 10 ** ((b - a) / 400))

# ======================
# 💰 EV + Kelly
# ======================
def ev(p, odds):
    return p * odds - 1

def kelly(p, odds):
    b = odds - 1
    q = 1 - p
    return max(0, (b * p - q) / b) * 0.5

# ======================
# 🖥️ UI
# ======================
st.title("⚽ Xu Football Model v10 (Pro)")

if st.button("🚀 Run Analysis"):

    matches = get_matches()
    results = []

    for m in matches:
        try:
            home = m.get("home_team")
            away = m.get("away_team")
            time = m.get("commence_time")

            odds = parse_odds(m)

            h_odds = odds.get(home, 2.0)
            a_odds = odds.get(away, 2.0)

            # 📊 Data
            form_h = get_team_form(home)
            form_a = get_team_form(away)
            h2h = get_h2h()
            elo_p = elo_prob(elo(home), elo(away))

            # 📊 Model Fusion
            p_h = (elo_p * 0.4) + (form_h * 0.3) + (h2h * 0.3)
            p_a = 1 - p_h

            ev_h = ev(p_h, h_odds)
            ev_a = ev(p_a, a_odds)

            if ev_h > ev_a:
                pick = "HOME"
                p = p_h
                odds_v = h_odds
                ev_v = ev_h
            else:
                pick = "AWAY"
                p = p_a
                odds_v = a_odds
                ev_v = ev_a

            k = kelly(p, odds_v)

            # 🚫 Filter bad bets（關鍵）
            if ev_v < 0:
                continue

            results.append({
                "Match": f"{home} vs {away}",
                "Date": time,
                "Pick": pick,
                "Odds": round(odds_v, 2),
                "WinRate": round(p, 3),
                "EV": round(ev_v, 3),
                "Kelly": round(k, 3),
                "Form(H)": round(form_h, 2),
                "Form(A)": round(form_a, 2)
            })

        except:
            continue

    df = pd.DataFrame(results)

    if df.empty:
        st.error("❌ No value bets found (24h)")
    else:
        st.success("✅ Top Value Bets (24h)")
        st.dataframe(df.sort_values("EV", ascending=False).head(10))
