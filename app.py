import streamlit as st
import streamlit.components.v1 as components  # 導入 HTML 元件組件
import pandas as pd
import numpy as np
import math

# ==========================================
# 🎨 1. 配置與 CSS (定義為字串供 HTML 使用)
# ==========================================
st.set_page_config(page_title="MATCH PREDICT PRO v7.5", layout="wide")

COMMON_STYLE = """
<style>
    body { background-color: #05070a; color: #e0e0e0; font-family: sans-serif; margin: 0; padding: 10px; }
    .match-card { 
        background: #0d1117; border: 1px solid #30363d; border-radius: 12px; 
        padding: 20px; margin-bottom: 20px;
    }
    .header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #333; padding-bottom: 10px; }
    .league-tag { color: #f1c40f; font-size: 0.8rem; font-weight: bold; }
    .match-title { font-size: 1.4rem; color: #fff; margin: 5px 0; }
    .status-badge { color: #00ff88; font-weight: bold; font-size: 0.9rem; }
    .metric-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin: 15px 0; }
    .metric-box { background: #161b22; padding: 10px; border-radius: 8px; text-align: center; border: 1px solid #21262d; }
    .info-label { color: #888; font-size: 0.7rem; display: block; margin-bottom: 4px; }
    .data-val { font-weight: bold; color: #fff; font-size: 0.95rem; }
    .odds-table { width: 100%; border-collapse: collapse; margin-top: 10px; background: rgba(255,255,255,0.02); }
    .odds-table th { color: #888; font-size: 0.75rem; padding: 10px; border-bottom: 1px solid #333; text-align: center; }
    .odds-table td { text-align: center; padding: 12px; border-bottom: 1px solid #1b2129; font-size: 1rem; }
    .score-matrix { display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px; margin-top: 10px; }
    .score-item { background: #1c2128; padding: 8px; border-radius: 4px; text-align: center; font-size: 0.8rem; }
</style>
"""

# ==========================================
# 🧠 2. 核心分析邏輯
# ==========================================
class QuantumCore:
    def poisson_prob(self, lmbda, k):
        return (np.power(lmbda, k) * np.exp(-lmbda)) / math.factorial(k)

    def analyze(self, m):
        h_lmbda = m['h_exp'] * (0.88 if m['h_missing'] else 1.0)
        a_lmbda = m['a_exp'] * (0.88 if m['a_missing'] else 1.0)
        matrix = np.zeros((6, 6))
        for i in range(6):
            for j in range(6):
                matrix[i, j] = self.poisson_prob(h_lmbda, i) * self.poisson_prob(a_lmbda, j)
        
        h_p, d_p, a_p = np.sum(np.tril(matrix, -1)), np.sum(np.diag(matrix)), np.sum(np.triu(matrix, 1))
        o25 = 1 - (matrix[0,0] + matrix[0,1] + matrix[0,2] + matrix[1,0] + matrix[1,1] + matrix[2,0])
        ev = h_p - (1 / m['mkt_o'])
        return {"p": [h_p, d_p, a_p], "o25": o25, "ev": ev, "matrix": matrix}

# ==========================================
# 🏟️ 3. 數據源
# ==========================================
matches = [
    {
        "id": "1397", "league": "西甲", "h": "赫塔菲", "a": "萊萬特", 
        "h_exp": 1.4, "a_exp": 1.1, "h_missing": False, "a_missing": True, "mkt_o": 2.30,
        "h_rank": 8, "a_rank": 15, "h2h": "1勝 3和 1負", "formation": "5-4-1 vs 4-2-3-1"
    },
    {
        "id": "1402", "league": "意甲", "h": "費倫提那", "a": "拉齊奧", 
        "h_exp": 1.25, "a_exp": 1.55, "h_missing": True, "a_missing": False, "mkt_o": 2.85,
        "h_rank": 7, "a_rank": 5, "h2h": "0勝 2和 3負", "formation": "4-3-3 vs 4-2-3-1"
    }
]

# ==========================================
# 🖥️ 4. 渲染執行
# ==========================================
st.markdown("<h1 style='text-align:center; color:#00ff88;'>🛡️ MATCH PREDICT PRO v7.5</h1>", unsafe_allow_html=True)

core = QuantumCore()

for m in matches:
    res = core.analyze(m)
    
    # 這裡將整個卡片包裝成一個完整的 HTML 文件
    match_html = f"""
    {COMMON_STYLE}
    <div class="match-card">
        <div class="header">
            <div>
                <span class="league-tag">[{m['id']}] {m['league']}</span>
                <div class="match-title">{m['h']} VS {m['a']}</div>
            </div>
            <div class="status-badge">🎯 建議觀察</div>
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
                <td style="color:#00ff88; font-weight:bold;">{res['p'][0]:.1%}</td>
                <td>{res['p'][1]:.1%}</td>
                <td style="color:#ff4b4b; font-weight:bold;">{res['p'][2]:.1%}</td>
                <td style="color:#58a6ff; font-weight:bold;">{res['o25']:.1%}</td>
            </tr>
        </table>

        <p style="color:#888; font-size:0.8rem; margin: 15px 0 5px 0;">🔍 正確比數機率 (波膽預測)</p>
        <div class="score-matrix">
            <div class="score-item">1:0<br><b>{res['matrix'][1,0]:.1%}</b></div>
            <div class="score-item">2:0<br><b>{res['matrix'][2,0]:.1%}</b></div>
            <div class="score-item">2:1<br><b>{res['matrix'][2,1]:.1%}</b></div>
            <div class="score-item">1:1<br><b>{res['matrix'][1,1]:.1%}</b></div>
            <div class="score-item">0:1<br><b>{res['matrix'][0,1]:.1%}</b></div>
        </div>
    </div>
    """
    # 關鍵修正：使用 components.html 強制渲染，不走 markdown 引擎
    components.html(match_html, height=450, scrolling=False)

st.caption("v7.5 採用 Component 沙盒渲染技術，已解決 HTML 代碼外露問題。")
