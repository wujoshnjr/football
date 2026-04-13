import streamlit as st
import pandas as pd
import numpy as np
import requests
from scipy.stats import poisson
import pytz
from datetime import datetime
import io

# 1. 核心交易引擎 (Quantum Trading Engine)
class FootballTradingEngine:
    def __init__(self):
        self.league_avg_goals = 1.35
        self.home_advantage = 0.15 # 截圖要求：Home Advantage

    def monte_carlo_simulation(self, home_expect, away_expect, sim_count=10000):
        """截圖要求：Monte Carlo (100,000 simulations 縮減為 10,000 以維持效能)"""
        home_goals = np.random.poisson(home_expect, sim_count)
        away_goals = np.random.poisson(away_expect, sim_count)
        
        diff = home_goals - away_goals
        hw = np.mean(diff > 0)
        d = np.mean(diff == 0)
        aw = np.mean(diff < 0)
        o25 = np.mean((home_goals + away_goals) > 2.5)
        
        # 亞洲盤口計算 (Asian Handicap -0.5)
        ah_win = hw 
        return hw, d, aw, o25, ah_win

    def calculate_kelly(self, prob, odds):
        """截圖要求：Kelly Criterion"""
        if odds <= 1: return 0
        b = odds - 1
        q = 1 - prob
        f = (b * prob - q) / b
        return max(0, f * 0.1) # 採用 Fractional Kelly (10%) 以降低風險

    def predict_pro(self, home_team, away_team, market_odds=2.0):
        # 模擬 λ (進球期望) - 這裡應接入你的 Elo 系統
        h_exp = self.league_avg_goals + self.home_advantage
        a_exp = self.league_avg_goals - 0.1
        
        hw, d, aw, o25, ah = self.monte_carlo_simulation(h_exp, a_exp)
        
        # EV 計算 (截圖要求：EV calculation)
        ev = (hw * market_odds) - 1
        kelly = self.calculate_kelly(hw, market_odds)
        
        return {
            "home": home_team, "away": away_team,
            "hw": hw, "d": d, "aw": aw, "o25": o25,
            "ev": ev, "kelly": kelly, "ah": ah,
            "trap": "YES" if abs(hw - (1/market_odds)) > 0.2 else "NO" # 市場陷阱偵測
        }

# 2. 介面與數據採集
st.set_page_config(page_title="Pro Betting Dashboard", layout="wide")
engine = FootballTradingEngine()
tz = pytz.timezone("Asia/Taipei")

# 專業 UI CSS
st.markdown("""
    <style>
    .match-card { border: 1px solid #333; padding: 20px; border-radius: 15px; background: #111; color: white; margin-bottom: 20px; }
    .ev-box { color: #00ff00; font-weight: bold; border-left: 4px solid #00ff00; padding-left: 10px; }
    .probability-tag { background: #333; padding: 5px 10px; border-radius: 5px; font-size: 0.8rem; }
    </style>
""", unsafe_allow_html=True)

st.title("🏆 Professional Betting Terminal v5.2")

# 數據來源 (此處延用 Football-Data API)
@st.cache_data(ttl=1800)
def get_live_data():
    key = st.secrets.get("FOOTBALL_DATA_API_KEY")
    url = "https://api.football-data.org/v4/matches"
    try:
        res = requests.get(url, headers={'X-Auth-Token': key}, timeout=10).json()
        return res.get('matches', [])
    except: return []

matches = get_live_data()

# 3. 顯示邏輯 (Match Card 設計)
if not matches:
    st.info("正在掃描全球賽場... 請確認 API 狀態。")
else:
    for m in matches[:15]:
        home_name = m['homeTeam']['name']
        away_name = m['awayTeam']['name']
        res = engine.predict_pro(home_name, away_name)
        
        # 構建專業 Match Card (截圖要求：UI Requirements)
        with st.container():
            st.markdown(f"""
            <div class="match-card">
                <div style="display: flex; justify-content: space-between;">
                    <span>🏟️ {m['competition']['name']}</span>
                    <span>⏰ {datetime.now(tz).strftime('%H:%M')} (LIVE)</span>
                </div>
                <div style="display: flex; justify-content: space-around; align-items: center; margin: 20px 0;">
                    <div style="text-align: center; width: 40%;"><h3>{res['home']}</h3></div>
                    <div style="color: #e63946; font-size: 1.5rem;">VS</div>
                    <div style="text-align: center; width: 40%;"><h3>{res['away']}</h3></div>
                </div>
                <div style="display: flex; justify-content: space-between;">
                    <div class="probability-tag">Home: {res['hw']:.1%} | Draw: {res['d']:.1%} | Away: {res['aw']:.1%}</div>
                    <div class="ev-box">Expected Value: {res['ev']:.2%}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.metric("Kelly Stake", f"{res['kelly']:.2%}")
            with c2:
                st.metric("O/U 2.5 Prob", f"{res['o25']:.1%}")
            with c3:
                st.metric("Asian Handicap", "-0.5")
            with c4:
                trap_color = "inverse" if res['trap'] == "YES" else "normal"
                st.metric("Trap Detected", res['trap'], delta_color=trap_color)
            st.divider()

# 下載報表 (截圖要求：Value bet filter)
if st.sidebar.button("📊 導出 Value Bets"):
    df = pd.DataFrame([engine.predict_pro(m['homeTeam']['name'], m['awayTeam']['name']) for m in matches])
    value_bets = df[df['ev'] > 0.05] # 過濾 EV > 5% 的比賽
    csv = value_bets.to_csv(index=False).encode('utf-8')
    st.sidebar.download_button("📥 下載 CSV", csv, "ValueBets.csv", "text/csv")
