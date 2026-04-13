import streamlit as st
import pandas as pd
import numpy as np
import math
from datetime import datetime

# ==========================================
# 🎨 1. 專業交易 UI 配置 (修復 CSS 與全域風格)
# ==========================================
st.set_page_config(page_title="MATCH PREDICT PRO v7.4", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #05070a; color: #e0e0e0; }
    .main-header { font-size: 2.2rem; color: #00ff88; font-weight: 800; text-align: center; margin-bottom: 25px; }
    .match-card { 
        background: #0d1117; border: 1px solid #30363d; border-radius: 12px; 
        padding: 20px; margin-bottom: 25px; 
    }
    .metric-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin: 15px 0; }
    .metric-box { background: #161b22; padding: 10px; border-radius: 8px; text-align: center; border: 1px solid #21262d; }
    .info-label { color: #888; font-size: 0.75rem; display: block; }
    .data-val { font-weight: bold; color: #fff; font-size: 1rem; }
    .odds-table { width: 100%; border-collapse: collapse; margin-top: 15px; }
    .odds-table th { color: #888; font-size: 0.8rem; padding: 8px; border-bottom: 1px solid #333; }
    .odds-table td { text-align: center; padding: 12px; border-bottom: 1px solid #1b2129; }
    .prob-up { color: #00ff88; font-weight: bold; }
    .prob-down { color: #ff4b4b; font-weight: bold; }
    .score-matrix-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px; padding: 15px; background: #161b22; border-radius: 8px; }
    .score-item { text-align: center; font-size: 0.85rem; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 🧠 2. 核心分析引擎 (修正 NumPy Factorial)
# ==========================================
class QuantumEngineV7:
    def poisson_prob(self, lmbda, k):
        return (np.power(lmbda, k) * np.exp(-lmbda)) / math.factorial(k)

    def analyze(self, m):
        # Lambda 傷停修正 (實戰邏輯)
        h_lmbda = m['h_exp'] * (0.88 if m['h_missing'] else 1.0)
        a_lmbda = m['a_exp'] * (0.88 if m['a_missing'] else 1.0)
        
        # 矩陣計算
        matrix = np.zeros((6, 6))
        for i in range(6):
            for j in range(6):
                matrix[i, j] = self.poisson_prob(h_lmbda, i) * self.poisson_prob(a_lmbda, j)
        
        # 玩法機率
        h_win = np.sum(np.tril(matrix, -1))
        draw = np.sum(np.diag(matrix))
        a_win = np.sum(np.triu(matrix, 1))
        o25 = 1 - (matrix[0,0] + matrix[0,1] + matrix[0,2] + matrix[1,0] + matrix[1,1] + matrix[2,0])
        
        # 誘盤偵測
        mkt_p = 1 / m['mkt_o']
        ev = h_win - mkt_p
        status = "🎯 推薦" if ev > 0.05 else "⏳ 觀望"
        if abs(ev) > 0.15: status = "⛔ 誘盤警告"

        return {"p": [h_win, draw, a_win], "o25": o25, "ev": ev, "matrix": matrix, "status": status}

# ==========================================
# 🏟️ 3. 多場次數據 (同步台彩官網資訊)
# ==========================================
matches = [
    {
        "id": "1397", "league": "西甲", "h": "赫塔菲", "a": "萊萬特", 
        "h_exp": 1.4, "a_exp": 1.1, "h_missing": False, "a_missing": True, "mkt_o": 2.30,
        "h_rank": 8, "a_rank": 15, "h2h": "1勝 3和 1負", "formation": "5-4-1 vs 4-2-3-1"
    },
    {
        "id": "1402", "league": "意甲", "h": "費倫提那", "a": "拉齊奧", 
        "h_exp": 1.3, "a_exp": 1.6, "h_missing": True, "a_missing": False, "mkt_o": 2.80,
        "h_rank": 7, "a_rank": 5, "h2h": "0勝 2和 3負", "formation": "4-3-3 vs 4-2-3-1"
    }
]

# ==========================================
# 🖥️ 4. 介面渲染 (修正 HTML 顯示錯誤)
# ==========================================
st.markdown('<div class="main-header">🛡️ MATCH PREDICT PRO v7.4</div>', unsafe_allow_html=True)

engine = QuantumEngineV7()

for m in matches:
    res = engine.analyze(m)
    
    # 使用 f-string 構建完整的 HTML 卡片，避免 markdown 渲染中斷
    card_html = f"""
    <div class="match-card">
        <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #333; padding-bottom:10px;">
            <div>
                <span style="color:#f1c40f; font-size:0.8rem;">[{m['id']}] {m['league']}</span><br>
                <b style="font-size:1.3rem;">{m['h']} VS {m['a']}</b>
            </div>
            <div style="color:#00ff88; font-weight:bold;">{res['status']}</div>
        </div>

        <div class="metric-grid">
            <div class="metric-box"><span class="info-label">聯賽排名</span><span class="data-val">#{m['h_rank']} vs #{m['a_rank']}</span></div>
            <div class="metric-box"><span class="info-label">歷史對戰</span><span class="data-val">{m['h2h']}</span></div>
            <div class="metric-box"><span class="info-label">預計陣型</span><span class="data-val">{m['formation']}</span></div>
            <div class="metric-box"><span class="info-label">市場 EV</span><span class="data-val">{res['ev']:.2%}</span></div>
        </div>

        <table class="odds-table">
            <tr><th>玩法類型</th><th>主勝 (1)</th><th>和局 (X)</th><th>客勝 (2)</th><th>大 2.5</th></tr>
            <tr>
                <td><b>模型機率</b></td>
                <td class="prob-up">{res['p'][0]:.1%}</td>
                <td>{res['p'][1]:.1%}</td>
                <td class="prob-down">{res['p'][2]:.1%}</td>
                <td style="color:#58a6ff; font-weight:bold;">{res['o25']:.1%}</td>
            </tr>
        </table>
        
        <div style="margin-top:15px;">
            <p style="color:#888; font-size:0.8rem; margin-bottom:8px;">🔍 正確比數矩陣預測 (波膽)</p>
            <div class="score-matrix-grid">
                <div class="score-item"><small>1:0</small><br><b>{res['matrix'][1,0]:.1%}</b></div>
                <div class="score-item"><small>2:0</small><br><b>{res['matrix'][2,0]:.1%}</b></div>
                <div class="score-item"><small>2:1</small><br><b>{res['matrix'][2,1]:.1%}</b></div>
                <div class="score-item"><small>1:1</small><br><b>{res['matrix'][1,1]:.1%}</b></div>
                <div class="score-item"><small>0:1</small><br><b>{res['matrix'][0,1]:.1%}</b></div>
            </div>
        </div>
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)

# 底部免責聲明
st.caption("數據僅供分析參考，請理性購買彩券。")
