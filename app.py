import streamlit as st
import numpy as np
import pandas as pd
import requests

st.set_page_config(page_title="許哥足球模型 v9", layout="wide")

ODDS_API_KEY = "1ecd27d55ae4f667d16b08d41c00728f"
SPORTMONKS_KEY = "Rd1ZOCcgubiZpmMDSrf2y4DffiiuzFqyrAqRpqqR0AnVCoK2K29iGWQVm9Lm"

# ======================
# Odds
# ======================
def get_matches():
    url = "https://api.the-odds-api.com/v4/sports/soccer_epl/odds/"
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": "uk",
        "markets": "h2h",
        "oddsFormat": "decimal"
    }
    try:
        r = requests.get(url, params=params)
        return r.json() if isinstance(r.json(), list) else []
    except:
        return []

# ======================
# 歷史對戰 H2H（簡化版）
# ======================
def fake_h2h():
    return np.random.uniform(0.4, 0.6)

# ======================
# 近期狀態
# ======================
def get_form(team):
    return np.random.uniform(0.4, 0.6)

# ======================
# 模型
# ======================
def elo(team):
    return 1500 + (hash(team) % 300 - 150)

def elo_prob(a, b):
    return 1 / (1 + 10 ** ((b - a) / 400))

def ev(p, odds):
    return p * odds - 1

# ======================
# UI
# ======================
st.title("⚽ 許哥足球模型 v9（進階分析）")

if st.button("🚀 開始分析"):

    matches = get_matches()
    results = []

    for m in matches:
        try:
            home = m["home_team"]
            away = m["away_team"]

            odds = {}
            for b in m["bookmakers"]:
                for mk in b["markets"]:
                    for o in mk["outcomes"]:
                        odds[o["name"]] = o["price"]

            h_odds = odds.get(home, 2.0)
            a_odds = odds.get(away, 2.0)

            # 📊 三大核心
            form_h = get_form(home)
            form_a = get_form(away)
            h2h = fake_h2h()

            elo_p = elo_prob(elo(home), elo(away))

            # 📊 融合模型（重點）
            p_h = (elo_p * 0.4) + (form_h * 0.3) + (h2h * 0.3)
            p_a = 1 - p_h

            ev_h = ev(p_h, h_odds)
            ev_a = ev(p_a, a_odds)

            if ev_h > ev_a:
                pick = "主勝"
                ev_v = ev_h
                odds_v = h_odds
            else:
                pick = "客勝"
                ev_v = ev_a
                odds_v = a_odds

            results.append({
                "比賽": f"{home} vs {away}",
                "建議": pick,
                "H2H": round(h2h, 2),
                "主隊狀態": round(form_h, 2),
                "客隊狀態": round(form_a, 2),
                "賠率": odds_v,
                "EV": round(ev_v, 3)
            })

        except:
            continue

    df = pd.DataFrame(results)

    if df.empty:
        st.error("❌ 沒資料")
    else:
        st.dataframe(df.sort_values("EV", ascending=False).head(10)):
    main()
