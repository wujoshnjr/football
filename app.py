import streamlit as st
import streamlit.components.v1 as components
import numpy as np
import math
from datetime import datetime

# ==========================================
# 🎨 1. 職業級交易介面 CSS (重新定義視覺權重)
# ==========================================
st.set_page_config(page_title="MATCH PREDICT PRO v8.0", layout="wide")

PRO_STYLE = """
<style>
    body { background-color: #05070a; color: #e0e0e0; font-family: 'Inter', sans-serif; margin: 0; padding: 10px; }
    .match-card { 
        background: linear-gradient(145deg, #0d1117, #161b22); 
        border: 1px solid #30363d; border-radius: 16px; 
        padding: 24px; margin-bottom: 25px; box-shadow: 0 4px 20px rgba(0,0,0,0.5);
    }
    .header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; }
    .league-info { color: #8b949e; font-size: 0.85rem; font-weight: 600; text-transform: uppercase; }
    .match-title { font-size: 1.8rem; color: #fff; font-weight: 800; margin: 5px 0; }
    
    /* 核心指標高亮 */
    .ev-badge { padding: 6px 12px; border-radius: 6px; font-weight: bold; font-size: 0.85rem; }
    .ev-positive { background: rgba(0, 255, 136, 0.15); color: #00ff88; border: 1px solid #00ff88; }
    .ev-negative { background: rgba(255, 75, 75, 0.15); color: #ff4b4b; border: 1px solid #ff4b4b; }

    /* 近期走勢 W-D-L */
    .form-dot { display: inline-block; width: 18px; height: 18px; line-height: 18px; border-radius: 4px; 
                text-align: center; font-size: 0.7rem; font-weight: bold; margin-right: 3px; color: #000; }
    .w { background: #00ff88; } .d { background: #8b949e; } .l { background: #ff4b4b; }

    /* 數據網格 */
    .metric-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin: 20px 0; }
    .metric-box { background: rgba(255,255,255,0.03); padding: 12px; border-radius: 10px; border: 1px solid #21262d; }
    .info-label { color: #8b949e; font-size: 0.75rem; display: block; margin-bottom: 6px; }
    .data-val { font-weight: bold; color: #fff; font-size: 1rem; }

    /* 長條圖化正確比分 */
    .bar-container { margin-top: 5px; background: #21262d; border-radius: 4px; height: 8px; width: 100%; overflow: hidden; }
    .bar-fill { background: #58a6ff; height: 100%; border-radius: 4px; transition: width 0.3s; }
    .score-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; font-size: 0.85rem; }
</style>
"""

# ==========================================
# 🧠 2. 核心計算引擎 (含深度邏輯)
# ==========================================
class ProEngine:
    def analyze(self, m):
        # 傷停影響 Lambda 修正
        h_lmbda = m['h_exp'] * (0.85 if m['h_injury'] else 1.0)
        a_lmbda = m['a_exp'] * (0.85 if m['a_injury'] else 1.0)
        
        matrix = np.zeros((6, 6))
        for i in range(6):
            for j in range(6):
                matrix[i, j] = (np.power(h_lmbda, i) * np.exp(-h_lmbda) / math.factorial(i)) * \
                               (np.power(a_lmbda, j) * np.exp(-a_lmbda) / math.factorial(j))
        
        h_p, d_p, a_p = np.sum(np.tril(matrix, -1)), np.sum(np.diag(matrix)), np.sum(np.triu(matrix, 1))
        o25 = 1 - (matrix[0,0] + matrix[0,1] + matrix[0,2] + matrix[1,0] + matrix[1,1] + matrix[2,0])
        
        # 市場 EV 與行動建議
        mkt_p = 1 / m['mkt_o']
        ev = h_p - mkt_p
        if ev > 0.08: advice, a_class = "🔥 高價值推薦", "ev-positive"
        elif ev < -0.05: advice, a_class = "⚠️ 風險避開", "ev-negative"
        else: advice, a_class = "⏳ 建議觀望", ""
        
        return {"p": [h_p, d_p, a_p], "o25": o25, "ev": ev, "matrix": matrix, "advice": advice, "a_class": a_class}

# ==========================================
# 🏟️ 3. 深度模擬數據 (整合 Content 維度)
# ==========================================
matches = [
    {
        "id": "1397", "league": "西甲 - 第 31 輪", "h": "赫塔菲", "a": "萊萬特", 
        "h_exp": 1.45, "a_exp": 1.15, "h_injury": False, "a_injury": True, "mkt_o": 2.15,
        "h_rank": "8 (主場第5)", "a_rank": "15 (客場第18)", 
        "h_form": "WWDWL", "a_form": "LLDLL",
        "formation": "5-4-1", "style": "防守反擊", "up_time": "17:30 (預測)"
    }
]

# ==========================================
# 🖥️ 4. 渲染執行
# ==========================================
st.markdown("<h1 style='text-align:center; color:#00ff88; font-weight:900;'>🛡️ MATCH PREDICT PRO v8.0</h1>", unsafe_allow_html=True)

engine = ProEngine()

for m in matches:
    res = engine.analyze(m)
    
    # 格式化 Form HTML
    def get_form_html(form_str):
        html = ""
        for s in form_str:
            c = s.lower()
            html += f'<span class="form-dot {c}">{s}</span>'
        return html

    # 格式化正確比數 Bar Chart HTML
    scores = [("1:0", res['matrix'][1,0]), ("2:0", res['matrix'][2,0]), ("2:1", res['matrix'][2,1]), ("1:1", res['matrix'][1,1]), ("0:1", res['matrix'][0,1])]
    scores_html = ""
    for label, prob in scores:
        scores_html += f"""
        <div style="margin-bottom:12px;">
            <div class="score-row"><span>{label}</span><b>{prob:.1%}</b></div>
            <div class="bar-container"><div class="bar-fill" style="width:{prob*100*3}%"></div></div>
        </div>"""

    card_html = f"""
    {PRO_STYLE}
    <div class="match-card">
        <div class="header">
            <div>
                <span class="league-info">{m['league']} • {m['up_time']}</span>
                <div class="match-title">{m['h']} VS {m['a']}</div>
                <div style="margin-top:8px;">{get_form_html(m['h_form'])} <span style="color:#444; margin:0 10px;">vs</span> {get_form_html(m['a_form'])}</div>
            </div>
            <div class="ev-badge {res['a_class']}">{res['advice']}</div>
        </div>

        <div class="metric-grid">
            <div class="metric-box"><span class="info-label">主/客排名</span><span class="data-val">{m['h_rank']} / {m['a_rank']}</span></div>
            <div class="metric-box"><span class="info-label">陣型風格</span><span class="data-val">{m['formation']} ({m['style']})</span></div>
            <div class="metric-box"><span class="info-label">市場 EV</span><span class="data-val" style="color:#f1c40f;">{res['ev']:.2%}</span></div>
            <div class="metric-box"><span class="info-label">關鍵傷停</span><span class="data-val">{"❌ 無" if not m['h_injury'] else "⚠️ 有"} / {"⚠️ 有" if m['a_injury'] else "❌ 無"}</span></div>
        </div>

        <div style="display:grid; grid-template-columns: 1.5fr 1fr; gap:30px; margin-top:20px;">
            <div>
                <span class="info-label">📊 核心勝平負機率 (模型預測)</span>
                <table style="width:100%; margin-top:10px; border-spacing: 0 8px; border-collapse: separate;">
                    <tr>
                        <td style="background:#161b22; padding:15px; border-radius:8px; text-align:center;">
                            <span class="info-label">主勝</span><b style="font-size:1.4rem; color:#00ff88;">{res['p'][0]:.1%}</b>
                        </td>
                        <td style="background:#161b22; padding:15px; border-radius:8px; text-align:center;">
                            <span class="info-label">平局</span><b style="font-size:1.4rem;">{res['p'][1]:.1%}</b>
                        </td>
                        <td style="background:#161b22; padding:15px; border-radius:8px; text-align:center;">
                            <span class="info-label">客勝</span><b style="font-size:1.4rem; color:#ff4b4b;">{res['p'][2]:.1%}</b>
                        </td>
                    </tr>
                </table>
                <div style="background:#161b22; padding:12px; border-radius:8px; margin-top:10px; text-align:center;">
                    <span class="info-label">進球大 2.5 機率</span><b style="color:#58a6ff;">{res['o25']:.1%}</b>
                </div>
            </div>
            
            <div>
                <span class="info-label">🎯 正確比數視覺化 (波膽)</span>
                <div style="margin-top:10px;">{scores_html}</div>
            </div>
        </div>
    </div>
    """
    components.html(card_html, height=520, scrolling=False)
