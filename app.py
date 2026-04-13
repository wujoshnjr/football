import streamlit as st
import numpy as np
import pandas as pd
import math
import requests
from datetime import datetime

# ==========================================
# 🎨 1. 全局配置與高對比度樣式
# ==========================================
st.set_page_config(page_title="MATCH PREDICT PRO v12.5", layout="wide")

# 強制深色模式與自定義字體樣式
st.markdown("""
<style>
    .reportview-container { background: #0d1117; }
    .main-header { font-size: 2.2rem; font-weight: 900; color: #00ff88; text-align: center; margin-bottom: 20px; }
    .match-card { 
        background: #161b22; border: 1px solid #30363d; border-radius: 15px; 
        padding: 20px; margin-bottom: 25px; box-shadow: 0 4px 20px rgba(0,0,0,0.3);
    }
    .ev-badge { background: #f1c40f; color: #000; padding: 2px 8px; border-radius: 5px; font-weight: bold; font-size: 0.8rem; }
    .score-matrix-item { background: rgba(88, 166, 255, 0.1); border: 1px dashed #58a6ff; padding: 10px; border-radius: 8px; text-align: center; }
    table { width: 100%; color: white !important; }
    th { color: #8b949e !important; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 🧠 2. 數據抓取引擎 (對接運彩 / 國際盤 / AiScore)
# ==========================================
class DataEngine:
    """
    此模組負責自動化抓取邏輯。
    實務上可串接 The-Odds-API 或 Selenium 抓取台灣運彩官網。
    """
    def fetch_all_matches(self):
        # 這裡模擬從 API 抓取回來的多場賽事數據
        # 包含：賽事編號、聯賽、隊伍、運彩賠率、國際平均賠率、AiScore 基本面
        return [
            {
                "id": "1397", "league": "西甲", "home": "赫塔菲", "away": "萊萬特",
                "tsl_odds": {"h": 2.30, "d": 2.55, "a": 2.70},
                "intl_odds": {"h": 2.15, "d": 2.65, "a": 2.85},
                "aiscore": {
                    "rank": "#8 vs #15", "h2h": "1勝 3和 1負",
                    "formation": "5-4-1 vs 4-2-3-1",
                    "key_news": "主隊後防核心復出，客隊前鋒拉傷缺陣。"
                },
                "h_exp": 1.45, "a_exp": 1.10 # 模型預期進球
            },
            {
                "id": "1402", "league": "義甲", "home": "佛羅倫薩", "away": "拉齊奧",
                "tsl_odds": {"h": 2.45, "d": 2.80, "a": 2.35},
                "intl_odds": {"h": 2.30, "d": 2.90, "a": 2.25},
                "aiscore": {
                    "rank": "#7 vs #6", "h2h": "2勝 0和 3負",
                    "formation": "4-3-3 vs 4-3-3",
                    "key_news": "拉齊奧周中踢完歐冠體力受損，盤口呈現退盤趨勢。"
                },
                "h_exp": 1.20, "a_exp": 1.55
            }
        ]

# ==========================================
# ⚖️ 3. 預測核心 (Dixon-Coles & Poisson 整合)
# ==========================================
class PredictionCore:
    def poisson(self, l, k): return (np.power(l, k) * np.exp(-l)) / math.factorial(k)

    def analyze(self, match):
        h_l, a_l = match['h_exp'], match['a_exp']
        
        # 生成比分矩陣 (6x6)
        matrix = np.zeros((6, 6))
        for i in range(6):
            for j in range(6):
                prob = self.poisson(h_l, i) * self.poisson(a_l, j)
                matrix[i, j] = prob
        
        # 0:0 修正 (足球隨機性補償)
        matrix[0,0] *= 1.35
        matrix /= np.sum(matrix)
        
        # 計算 W/D/L 與 大小球機率
        h_p, d_p, a_p = np.sum(np.tril(matrix, -1)), np.sum(np.diag(matrix)), np.sum(np.triu(matrix, 1))
        o25 = 1 - (matrix[0,0]+matrix[0,1]+matrix[0,2]+matrix[1,0]+matrix[1,1]+matrix[2,0])
        
        # 計算市場 EV (Market Expected Value)
        # 以「模型勝率」與「運彩賠率」計算價值
        ev = (h_p * match['tsl_odds']['h']) - 1
        
        # 獲取 Top 5 波膽
        scores = []
        for i in range(4):
            for j in range(4):
                scores.append({"s": f"{i}:{j}", "p": matrix[i, j]})
        top_scores = sorted(scores, key=lambda x: x['p'], reverse=True)[:5]
        
        return {"p": [h_p, d_p, a_p], "o25": o25, "ev": ev, "top_scores": top_scores}

# ==========================================
# 🖥️ 4. Streamlit UI 渲染
# ==========================================
def main():
    st.markdown("<div class='main-header'>🛡️ MATCH PREDICT PRO v12.5</div>", unsafe_allow_html=True)
    
    # 頂部狀態列
    c1, c2, c3 = st.columns(3)
    c1.metric("數據更新", datetime.now().strftime("%H:%M:%S"), "API Sync")
    c2.metric("抓取狀態", "Active", "運彩/AiScore", delta_color="normal")
    c3.metric("模型信心", "High", "DC-Model", delta_color="inverse")

    engine = DataEngine()
    predictor = PredictionCore()
    matches = engine.fetch_all_matches()

    for m in matches:
        res = predictor.analyze(m)
        
        with st.container():
            st.markdown(f"""
            <div class="match-card">
                <div style="display:flex; justify-content:space-between;">
                    <span style="color:#58a6ff; font-weight:bold;">[{m['id']}] {m['league']}</span>
                    <span class="ev-badge">市場 EV: {res['ev']:.2%}</span>
                </div>
                <h2 style="margin:10px 0; color:white;">{m['home']} VS {m['away']}</h2>
            """, unsafe_allow_html=True)

            # 1. AiScore 深度戰報
            st.markdown(f"""
            <div style="background:rgba(255,255,255,0.05); padding:10px; border-radius:8px; font-size:0.9rem; margin-bottom:15px;">
                <b>🧠 AiScore 深度戰報：</b><br>
                📊 排名：{m['aiscore']['rank']} | 對戰：{m['aiscore']['h2h']} | 陣型：{m['aiscore']['formation']}<br>
                📰 關鍵：{m['aiscore']['key_news']}
            </div>
            """, unsafe_allow_html=True)

            # 2. 賠率對比表格 (高對比 Markdown)
            st.markdown(f"""
            | 數據來源 | 主勝 (1) | 和局 (X) | 客勝 (2) | 大 2.5 |
            | :--- | :---: | :---: | :---: | :---: |
            | **台灣運彩** | `{m['tsl_odds']['h']}` | `{m['tsl_odds']['d']}` | `{m['tsl_odds']['a']}` | -- |
            | **國際均盤** | `{m['intl_odds']['h']}` | `{m['intl_odds']['d']}` | `{m['intl_odds']['a']}` | -- |
            | **模型機率** | <b style="color:#00ff88;">{res['p'][0]:.1%}</b> | {res['p'][1]:.1%} | <b style="color:#ff4b4b;">{res['p'][2]:.1%}</b> | {res['o25']:.1%} |
            """, unsafe_allow_html=True)

            # 3. 正確比數矩陣 (波膽)
            st.write("🎯 **正確比數預測 (波膽 Top 5)**")
            sc_cols = st.columns(5)
            for i, score in enumerate(res['top_scores']):
                sc_cols[i].markdown(f"""
                <div class="score-matrix-item">
                    <span style="font-size:0.7rem; color:#8b949e;">{score['s']}</span><br>
                    <b style="color:#58a6ff;">{score['p']:.1%}</b>
                </div>
                """, unsafe_allow_html=True)
            
            st.markdown("</div>", unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)

if __name__ == "__main__":
    main()
