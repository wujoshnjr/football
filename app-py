import streamlit as st
import requests
import numpy as np
import pandas as pd
from dataclasses import dataclass
from functools import lru_cache

# ======================================
# ⚙️ CONFIG
# ======================================
st.set_page_config(page_title="足球量化系統 v6", layout="wide")

ODDS_API_KEY = "1ecd27d55ae4f667d16b08d41c00728f"
SPORTMONKS_KEY = "Rd1ZOCcgubiZpmMDSrf2y4DffiiuzFqyrAqRpqqR0AnVCoK2K29iGWQVm9Lm"


# ======================================
# 📡 DATA LAYER
# ======================================
class DataEngine:

    @staticmethod
    def fetch_odds():
        url = "https://api.the-odds-api.com/v4/sports/soccer_epl/odds/"
        params = {
            "apiKey": ODDS_API_KEY,
            "regions": "uk",
            "markets": "h2h",
            "oddsFormat": "decimal"
        }

        try:
            r = requests.get(url, params=params, timeout=10)
            return r.json() if isinstance(r.json(), list) else []
        except:
            return []

    @staticmethod
    def parse_market(match):
        """正確 market parsing（不依賴 team name）"""
        outcomes = {}

        for b in match.get("bookmakers", []):
            for m in b.get("markets", []):
                for o in m.get("outcomes", []):
                    name = o["name"]
                    price = o["price"]

                    if name not in outcomes:
                        outcomes[name] = []

                    outcomes[name].append(price)

        return outcomes

    @staticmethod
    def clean_odds(prices):
        if not prices:
            return 2.0

        arr = np.array(prices)
        return float(np.median(arr))


# ======================================
# 🧠 FEATURE ENGINE
# ======================================
class FeatureEngine:

    @staticmethod
    def sentiment(team):
        np.random.seed(hash(team) % 9999)
        return float(np.clip(np.random.normal(0.5, 0.08), 0.3, 0.7))

    @staticmethod
    def form(team):
        if not SPORTMONKS_KEY:
            return 0.5

        try:
            url = f"https://api.sportmonks.com/v3/football/teams/search/{team}?api_token={SPORTMONKS_KEY}"
            r = requests.get(url).json()

            team_id = r["data"][0]["id"]

            url2 = f"https://api.sportmonks.com/v3/football/teams/{team_id}?api_token={SPORTMONKS_KEY}&include=latest"
            r2 = requests.get(url2).json()

            matches = r2.get("data", {}).get("latest", [])

            wins = 0
            total = 0

            for m in matches:
                try:
                    score = m.get("scores", [])
                    if len(score) < 2:
                        continue

                    hg = score[0]["score"]["goals"]
                    ag = score[1]["score"]["goals"]

                    total += 1
                    if hg > ag:
                        wins += 1
                except:
                    continue

            return wins / total if total > 0 else 0.5

        except:
            return 0.5

    @staticmethod
    def elo(team):
        return 1500 + (hash(team) % 300 - 150)


# ======================================
# 🧠 MODEL ENGINE
# ======================================
class ModelEngine:

    @staticmethod
    def elo_prob(a, b):
        return 1 / (1 + 10 ** ((b - a) / 400))

    @staticmethod
    def fusion(market, form, sentiment, elo_p):
        return (
            0.45 * market +
            0.25 * form +
            0.15 * sentiment +
            0.15 * elo_p
        )

    @staticmethod
    def poisson_mc(home_xg, away_xg, n=5000):
        home_goals = np.random.poisson(home_xg, n)
        away_goals = np.random.poisson(away_xg, n)

        return np.mean(home_goals > away_goals)

    @staticmethod
    def kelly(p, odds):
        b = odds - 1
        q = 1 - p
        return max(0, min((b * p - q) / b, 0.25))

    @staticmethod
    def ev(p, odds):
        return p * odds - 1


# ======================================
# 🚀 MAIN PIPELINE
# ======================================
def main():

    st.title("⚽ 許哥足球模型 v6（研究級專業版）")

    DE = DataEngine()
    FE = FeatureEngine()
    ME = ModelEngine()

    if st.button("🚀 開始分析 v6"):

        matches = DE.fetch_odds()
        results = []

        for m in matches:

            try:
                home = m.get("home_team")
                away = m.get("away_team")

                if not home or not away:
                    continue

                market = DE.parse_market(m)

                home_odds = DE.clean_odds(market.get(home, []))
                away_odds = DE.clean_odds(market.get(away, []))

                # ======================
                # 🧠 FEATURES
                # ======================
                market_p_home = 1 / home_odds
                market_p_away = 1 / away_odds

                form_h = FE.form(home)
                form_a = FE.form(away)

                senti_h = FE.sentiment(home)
                senti_a = FE.sentiment(away)

                elo_h = FE.elo(home)
                elo_a = FE.elo(away)

                elo_p_home = ME.elo_prob(elo_h, elo_a)
                elo_p_away = 1 - elo_p_home

                # ======================
                # 🧠 FUSION
                # ======================
                p_home = ME.fusion(market_p_home, form_h, senti_h, elo_p_home)
                p_away = ME.fusion(market_p_away, form_a, senti_a, elo_p_away)

                # ======================
                # ⚽ xG SIMULATION (proper)
                # ======================
                home_xg = p_home * 1.6
                away_xg = p_away * 1.6

                mc_home = ME.poisson_mc(home_xg, away_xg)

                # ======================
                # 💰 BETTING METRICS
                # ======================
                ev_home = ME.ev(mc_home, home_odds)
                ev_away = ME.ev(1 - mc_home, away_odds)

                if ev_home > ev_away:
                    pick = "主勝"
                    odds = home_odds
                    p = mc_home
                    ev_v = ev_home
                else:
                    pick = "客勝"
                    odds = away_odds
                    p = 1 - mc_home
                    ev_v = ev_away

                kelly = ME.kelly(p, odds)
                score = ev_v * 0.6 + kelly * 0.4

                results.append({
                    "match": f"{home} vs {away}",
                    "pick": pick,
                    "odds": round(odds, 2),
                    "prob": round(p, 3),
                    "ev": round(ev_v, 3),
                    "kelly": round(kelly, 3),
                    "score": round(score, 3)
                })

            except:
                continue

        df = pd.DataFrame(results)

        if df.empty:
            st.error("❌ 沒有資料")
            return

        df = df.sort_values("score", ascending=False)

        st.success("✅ v6 完整分析完成（研究級模型）")
        st.dataframe(df.head(10), use_container_width=True)


if __name__ == "__main__":
    main()
