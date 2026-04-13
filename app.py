import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import math  # 導入原生 math 模組以解決 np.math 消失的問題

# ==========================================
# 🎨 1. 專業交易 UI 配置 (修復渲染問題)
# ==========================================
st.set_page_config(page_title="MATCH PREDICT PRO v7.3", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #05070a; color: #e0e0e0; }
    .main-header { font-size: 2.5rem; color: #00ff88; font-weight: 800; text-align: center; margin-bottom: 25px; }
    .match-card { 
        background: #0d1117; border: 1px solid #30363d; border-radius: 12px; 
        padding: 25px; margin-bottom: 25px; 
    }
    .info-label { color: #888; font-size: 0.85rem; }
    .data-val { font-weight: bold; color: #fff; font-size: 1.1rem; }
    .metric-box { background: #161b22; padding: 12px; border-radius: 8px; text-align: center; border: 1px solid #21262d; }
    .odds-table { width: 100%; border-collapse: collapse; margin-top: 15px; }
    .odds-table th { color: #888; text-align: center; padding: 10px; border-bottom: 1px solid #333; }
    .odds-table td { text-align: center; padding: 12px; border-bottom: 1px solid #161b22; }
    .sig-badge { padding: 5px 15px; border-radius: 20px; font-weight: bold; font-size: 0.9rem; }
    .sig-recommend { background: rgba(0, 255, 136, 0.1); border: 1px solid #00ff88; color: #00ff88; }
    .sig-trap { background: rgba(255, 75, 75, 0.1); border: 1px solid #ff4b4b; color: #ff4b4b; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 🧠 2. 核心分析引擎 (修正 NumPy 錯誤)
# ==========================================
class QuantumEngine:
    def poisson_prob(self, lmbda, k):
        # 修正點：使用 math.factorial 替代 np.math.factorial
        return (np.power(lmbda, k) * np.exp(-lmbda)) / math.factorial(k)

    def analyze_match(self, m):
        # Lambda 修正邏輯 (整合傷停修正要求)
        h_lmbda = m['h_exp'] * (0.85 if m['h_missing'] else 1.0)
        a_lmbda = m['a_exp'] * (0.85 if m['a_missing'] else 1.0)
        
        # 建立 6x6 正確比數矩陣
        matrix = np.zeros((6, 6))
        for i in range(6):
            for j in range(6):
                matrix[i, j] = self.poisson_prob(h_lmbda, i) * self.poisson_prob(a_lmbda, j)
        
        # 計算不讓分機率
        h_win = np.sum(np.tril(matrix, -1))
        draw = np.sum(np.diag(matrix))
        a_win = np.sum(np.triu(matrix, 1))
        o25 = 1 - np.sum(matrix[0:2, 0:2]) - matrix[2,0] - matrix[0,2] # 簡化大2.5計算
        
        # 誘盤與 EV 偵測
        mkt_p = 1 / m['mkt_o']
        ev = h_win - mkt_p
        is_trap = abs(ev) > 0.12
        
        # 決策指令
        if ev > 0.06 and not is_trap:
            sig, s_class = "🎯 核心推薦：主勝", "sig-recommend"
        elif is_trap:
            sig, s_class = "⛔ 誘盤警告：背離過大", "sig-trap"
        else:
            sig, s_class = "⏳ 觀望：價值空間不足", ""
            
        return {"p": [h_win, draw, a_win], "o25": o25, "ev": ev, "sig": sig, "class": s_class, "matrix": matrix}

# ==========================================
# 🏟️ 3. 賽事數據庫 (多場次台彩風格)
# ==========================================
matches = [
    {
        "id": "1397", "league": "西甲", "h": "赫塔菲", "a": "萊萬特", 
        "h_exp": 1.45, "a_exp": 1.10, "h_missing": False, "a_missing": True, "mkt_o": 2.30,
        "h_rank": 8, "a_rank": 15, "h2h": "1勝 3和 1負", "formation": "5-4-1 vs 4-2-3-1"
    },
    {
        "id": "1402", "league": "意甲", "h": "費倫提那", "a": "拉齊奧", 
        "h_exp": 1.20, "a_exp": 1.60, "h_missing": True, "a_missing": False, "mkt_o": 2.80,
        "h_rank": 7, "a_rank": 5, "h2h": "0勝 2和 3負", "formation": "4-3-3 vs 4-2-3-1"
    }
]

# ==========================================
# 🖥️ 4. 介面渲染
# ==========================================
st.markdown('<div class="main-header">🛡️ MATCH PREDICT PRO v7.3</div>', unsafe_allow_html=True)

engine = QuantumEngine()

for m in matches:
    res = engine.analyze_match(m)
    
    st.markdown(f"""
    <div class="match-card">
        <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #333; padding-bottom:15px; margin-bottom:15px;">
            <div>
                <span style="color:#f1c40f; font-weight:bold;">[{m['id']}] {m['league']}</span><br>
                <b style="font-size:1.6rem;">{m['h']} VS {m['a']}</b>
            </div>
            <div class="sig-badge {res['class']}">{res['sig']}</div>
        </div>

        <div style="display:grid; grid-template-columns: repeat(4, 1fr); gap:15px; margin-bottom:20px;">
            <div class="metric-box"><span class="info-label">聯賽排名</span><br><span class="data-val">#{m['h_rank']} vs #{m['a_rank']}</span></div>
            <div class="metric-box"><span class="info-label">歷史對戰</span><br><span class="data-val">{m['h2h']}</span></div>
            <div class="metric-box"><span class="info-label">預計陣型</span><br><span class="data-val">{m['formation']}</span></div>
            <div class="metric-box"><span class="info-label">市場 EV</span><br><b style="color:#f1c40f;">{res['ev']:.2%}</b></div>
        </div>

        <table class="odds-table">
            <tr><th>玩法</th><th>主勝 (1)</th><th>和局 (X)</th><th>客勝 (2)</th><th>大 2.5</th></tr>
            <tr>
                <td><b>模型機率</b></td>
                <td><span style="color:#00ff88;">{res['p'][0]:.1%}</span></td>
                <td>{res['p'][1]:.1%}</td>
                <td><span style="color:#ff4b4b;">{res['p'][2]:.1%}</span></td>
                <td><b>{res['o25']:.1%}</b></td>
            </tr>
        </table>

        <details style="margin-top:15px;">
            <summary style="color:#888; cursor:pointer;">🔍 查看正確比數矩陣預測</summary>
            <div style="display:grid; grid-template-columns: repeat(5, 1fr); gap:10px; padding:15px; background:rgba(255,255,255,0.02); border-radius:8px; margin-top:10px;">
                <div style="text-align:center;"><small>1:0</small><br><b>{res['matrix'][1,0]:.1%}</b></div>
                <div style="text-align:center;"><small>2:0</small><br><b>{res['matrix'][2,0]:.1%}</b></div>
                <div style="text-align:center;"><small>2:1</small><br><b>{res['matrix'][2,1]:.1%}</b></div>
                <div style="text-align:center;"><small>1:1</small><br><b>{res['matrix'][1,1]:.1%}</b></div>
                <div style="text-align:center;"><small>0:1</small><br><b>{res['matrix'][0,1]:.1%}</b></div>
            </div>
        </details>
    </div>
    """, unsafe_allow_html=True)
