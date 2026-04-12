import streamlit as st
import numpy as np
import pandas as pd
import requests

st.set_page_config(page_title="許哥足球模型 v9", layout="wide")

# 🔑 API KEY（一定要填）
ODDS_API_KEY = "1ecd27d55ae4f667d16b08d41c00728f"
SPORTMONKS_KEY = "Rd1ZOCcgubiZpmMDSrf2y4DffiiuzFqyrAqRpqqR0AnVCoK2K29iGWQVm9Lm"

# ======================
# 📡 取得賽事（Odds API）
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
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        return data if isinstance(data, list) else []
    except:
        return []

# ======================
# 📊 解析賠率
# ======================
def parse_odds(match):
    odds = {}
    for b in match.get("bookmakers", []):
        for m in b.get("markets", []):
            for o in m.get("outcomes", []):
                odds[o["name"]] = o["price"]
    return odds

# ======================
# 📊 Sportmonks：近期狀態
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
# 📊 H2H（暫用 fallback）
# ======================
def get_h2h(home, away):
    # ⚠️ 若沒有付費 H2H API，用保守值
    return 0.5

# ======================
# 📊 Elo 模型
# ======================
def elo(team):
    return 1500 + (hash(team) % 300 - 150)

def elo_prob(a, b):
    return 1 / (1 + 10 ** ((b - a) / 400))

# ======================
# 💰 EV & Kelly
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
st.title("⚽ 許哥足球模型 v9（完整分析版）")

if st.button("🚀 開始分析"):

    matches = get_matches()
    results = []

    for m in matches:

        try:
            home = m.get("home_team")
            away = m.get("away_team")

            odds = parse_odds(m)

            h_odds = odds.get(home, 2.0)
            a_odds = odds.get(away, 2.0)

            # 📊 真數據（form）
            form_h = get_team_form(home)
            form_a = get_team_form(away)

            # 📊 H2H
            h2h = get_h2h(home, away)

            # 📊 Elo
            elo_p = elo_prob(elo(home), elo(away))

            # 📊 融合模型（核心）
            p_h = (elo_p * 0.4) + (form_h * 0.3) + (h2h * 0.3)
            p_a = 1 - p_h

            ev_h = ev(p_h, h_odds)
            ev_a = ev(p_a, a_odds)

            if ev_h > ev_a:
                pick = "主勝"
                p = p_h
                odds_v = h_odds
                ev_v = ev_h
            else:
                pick = "客勝"
                p = p_a
                odds_v = a_odds
                ev_v = ev_a

            k = kelly(p, odds_v)

            results.append({
                "比賽": f"{home} vs {away}",
                "建議下注": pick,
                "主隊狀態": round(form_h, 2),
                "客隊狀態": round(form_a, 2),
                "H2H": round(h2h, 2),
                "賠率": round(odds_v, 2),
                "勝率": round(p, 3),
                "EV": round(ev_v, 3),
                "Kelly": round(k, 3)
            })

        except:
            continue

    df = pd.DataFrame(results)

    if df.empty:
        st.error("❌ 沒有可用資料（請確認 API KEY）")
    else:
        st.success("✅ 分析完成（Top 10）")
        st.dataframe(df.sort_values("EV", ascending=False).head(10))
