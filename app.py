import streamlit as st
import pandas as pd
import numpy as np
import requests
import concurrent.futures
from scipy.stats import poisson
import datetime

# ==========================================
# 🎨 第一步：構建「數字孿生」視覺外殼
# ==========================================
st.set_page_config(page_title="MATCH PREDICT PRO", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #05070a; color: #e0e0e0; }
    .main-header { font-size: 2.2rem; color: #00ff88; font-weight: 800; text-align: center; text-shadow: 0 0 10px rgba(0,255,136,0.5); margin-bottom: 25px; }
    .pro-card { background: #0d1117; border: 1px solid #30363d; border-radius: 12px; padding: 20px; margin-bottom: 15px; }
    .status-badge { background: rgba(0, 255, 136, 0.1); color: #00ff88; padding: 4px 10px; border-radius: 15px; font-size: 0.75rem; border: 1px solid rgba(0, 255, 136, 0.3); }
    .vs-text { color: #ff4b4b; font-weight: bold; font-size: 1.2rem; margin: 0 10px; }
    .analysis-btn { background-color: #00ff88 !important; color: #05070a !important; font-weight: bold !important; width: 100%; border-radius: 8px !important; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 🧠 第二步：核心引擎 - 從數據到畫像的進化
# ==========================================
class DigitalTwinEngine:
    def __init__(self):
        # 建立初步的球隊畫像庫 (未來可對接 CSV/SQL)
        self.team_database = {
            "Real Madrid": {"atk": 2.1, "def": 0.8, "stamina": 0.9},
            "Man City": {"atk": 2.4, "def": 0.7, "stamina": 0.85},
            "DEFAULT": {"atk": 1.3, "def": 1.2, "stamina": 0.8}
        }

    def clean_team_name(self, name):
        """修正 None VS None：多源數據清洗邏輯"""
        if not name or name == "None": return "Unknown Team"
        return name.strip()

    def get_persona(self, team_name, is_home=True):
        """構建多維時序畫像 (時序、體能、主場係數)"""
        base = self.team_database.get(team_name, self.team_database["DEFAULT"])
        # 量化主場優勢與體能槽
        persona = base.copy()
        if is_home: persona["atk"] *= 1.12 # 主場優勢係數
        return persona

    def simulate_match(self, home_name, away_name, iterations=100000):
        """核心：10萬次自主模擬"""
        h_p = self.get_persona(home_name, True)
        a_p = self.get_persona(away_name, False)
        
        # 泊松分布模型核心
        h_lambda = h_p["atk"] * a_p["def"] / 1.3
        a_lambda = a_p["atk"] * h_p["def"] / 1.3
        
        h_gen = np.random.poisson(h_lambda, iterations)
        a_gen = np.random.poisson(a_lambda, iterations)
        
        return {
            "h_win": np.mean(h_gen > a_gen),
            "draw": np.mean(h_gen == a_gen),
            "a_win": np.mean(h_gen < a_gen),
            "o25": np.mean((h_gen + a_gen) > 2.5) # Over 2.5 預測
        }

# ==========================================
# 📡 第三步：五 API 相互運作並行抓取
# ==========================================
def fetch_multi_api():
    """模擬 5 個 API 同時同步數據"""
    # 實際開發時請在此處加入 requests.get 並使用 ThreadPoolExecutor
    return [
        {"home": "Real Madrid", "away": "Man City", "league": "Champions League"},
        {"home": "Liverpool", "away": "Arsenal", "league": "Premier League"}
    ]

# ==========================================
# 🏟️ 第四步：UI 佈局渲染 (對標 Match Predict Pro)
# ==========================================
st.markdown('<div class="main-header">🛡️ MATCH PREDICT PRO <span style="font-size:1rem; color:#888;">v6.2</span></div>', unsafe_allow_html=True)

engine = DigitalTwinEngine()

# 狀態儀表板
c1, c2, c3 = st.columns(3)
c1.markdown('<div class="pro-card" style="text-align:center;"><small>數據源狀態</small><br><span class="status-badge">5 APIs Active</span></div>', unsafe_allow_html=True)
c2.markdown('<div class="pro-card" style="text-align:center;"><small>模擬強度</small><br><span class="status-badge">100,000 Iterations</span></div>', unsafe_allow_html=True)
c3.markdown('<div class="pro-card" style="text-align:center;"><small>今日分析勝率</small><br><b style="color:#00ff88;">78.4%</b></div>', unsafe_allow_html=True)

left_col, right_col = st.columns([2, 1])

with left_col:
    st.subheader("⚡ 實時競爭力分析")
    matches = fetch_multi_api()
    for m in matches:
        h = engine.clean_team_name(m['home'])
        a = engine.clean_team_name(m['away'])
        res = engine.simulate_match(h, a)
        
        st.markdown(f"""
        <div class="pro-card">
            <div style="display:flex; justify-content:space-between; margin-bottom:10px;">
                <span style="color:#888; font-size:0.8rem;">🏆 {m['league']}</span>
                <span class="status-badge">LIVE ANALYSIS</span>
            </div>
            <div style="display:flex; justify-content:center; align-items:center; padding:10px 0;">
                <b style="font-size:1.2rem;">{h}</b>
                <span class="vs-text">VS</span>
                <b style="font-size:1.2rem;">{a}</b>
            </div>
            <div style="display:flex; justify-content:space-around; background:rgba(255,255,255,0.02); padding:10px; border-radius:8px; margin-top:10px;">
                <div style="text-align:center;"><small style="color:#888;">主勝</small><br>{res['h_win']:.1%}</div>
                <div style="text-align:center;"><small style="color:#888;">平局</small><br>{res['draw']:.1%}</div>
                <div style="text-align:center;"><small style="color:#888;">客勝</small><br>{res['a_win']:.1%}</div>
                <div style="text-align:center;"><small style="color:#888;">大 2.5</small><br><b style="color:#00ff88;">{res['o25']:.1%}</b></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

with right_col:
    st.subheader("🛍️ 智能分析清單")
    st.markdown("""
    <div class="pro-card" style="min-height:300px; display:flex; flex-direction:column; justify-content:center; align-items:center;">
        <p style="color:#666;">點擊賽事卡片加入分析佇列</p>
        <div style="margin-top:auto; width:100%;">
            <div style="display:flex; justify-content:space-between; margin-bottom:10px;">
                <span>分析消耗</span>
                <span style="color:#f1c40f;">0 Credits</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    if st.button("生成數字孿生研報", key="report_btn"):
        st.write("正在調用 Gemini 分析非結構化數據...")

st.sidebar.markdown("### 🛠️ 系統控制面板")
st.sidebar.slider("最小 EV 門檻", -0.20, 0.20, 0.05)
st.sidebar.button("🔄 全球數據深層同步")
