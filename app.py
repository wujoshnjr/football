import streamlit as st
import streamlit.components.v1 as components
import numpy as np
import math

# ==========================================
# 🎨 1. 職業級交易介面 CSS (整合 v8.0 視覺)
# ==========================================
st.set_page_config(page_title="MATCH PREDICT PRO v9.0", layout="wide")

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
    
    .ev-badge { padding: 6px 12px; border-radius: 6px; font-weight: bold; font-size: 0.85rem; }
    .ev-positive { background: rgba(0, 255, 136, 0.15); color: #00ff88; border: 1px solid #00ff88; }
    .ev-negative { background: rgba(255, 75, 75, 0.15); color: #ff4b4b; border: 1px solid #ff4b4b; }

    .form-dot { display: inline-block; width: 18px; height: 18px; line-height: 18px; border-radius: 4px; 
                text-align: center; font-size: 0.7rem; font-weight: bold; margin-right: 3px; color: #000; }
    .w { background: #00ff88; } .d { background: #8b949e; } .l { background: #ff4b4b; }

    .metric-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin: 20px 0; }
    .metric-box { background: rgba(255,255,255,0.03); padding: 12px; border-radius: 10px; border: 1px solid #21262d; }
    .info-label { color: #8b949e; font-size: 0.75rem; display: block; margin-bottom: 6px; }
    .data-val { font-weight: bold; color: #fff; font-size: 1rem; }

    .bar-container { margin-top: 5px; background: #21262d; border-radius: 4px; height: 8px; width: 100%; overflow: hidden; }
    .bar-fill { background: #58a6ff; height: 100%; border-radius: 4px; transition: width 0.3s; }
    .score-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; font-size: 0.85rem; }
</style>
"""

# ==========================================
# 🧠 2. 深度學習與進階數學引擎 (v9.0)
# ==========================================
class QuantumDeepEngine:
    def poisson(self, lmbda, k):
        return (np.power(lmbda, k) * np.exp(-lmbda)) / math.factorial(k)

    def analyze(self, m):
        # 1. 傷停與 ML 綜合權重修正
        h_lmbda = m['h_exp'] * (0.85 if m['h_injury'] else 1.0)
        a_lmbda = m['a_exp'] * (0.85 if m['a_injury'] else 1.0)
        
        # 2. 建立 7x7 矩陣以容納極端比分
        matrix = np.zeros((7, 7))
        for i in range(7):
            for j in range(7):
                prob = self.poisson(h_lmbda, i) * self.poisson(a_lmbda, j)
                
                # 【修正 A】肥尾效應 (Fat Tail)：賦予大於 3 球的極端比分額外 15% 權重
                if i >= 3 or j >= 3:
                    prob *= 1.15
                
                matrix[i, j] = prob
                
        # 【修正 B】Zero-Inflated (Dixon-Coles 近似)：修正 0:0 與平局低估問題
        matrix[0, 0] *= 1.35  # 強制拉高 0:0 發生機率 35%
        matrix[1, 1] *= 1.10  # 稍微拉高 1:1 機率 10%
        
        # 重新歸一化矩陣 (確保總機率為 100%)
        matrix /= np.sum(matrix)
        
        # 計算不讓分勝平負
        h_p, d_p, a_p = np.sum(np.tril(matrix, -1)), np.sum(np.diag(matrix)), np.sum(np.triu(matrix, 1))
        
        # 計算大小分 (精確計算 2.5 球以下，再反推大分)
        under_25 = matrix[0,0] + matrix[0,1] + matrix[0,2] + matrix[1,0] + matrix[1,1] + matrix[2,0]
        o25 = 1 - under_25
        
        # 統整極端大分機率 (任一方進 3 球以上)
        fat_tail_prob = np.sum(matrix[3:, :]) + np.sum(matrix[:, 3:]) - np.sum(matrix[3:, 3:])
        
        # 3. 盈利率公式與 Alpha 偵測
        mkt_p = 1 / m['mkt_o']
        ev = h_p - mkt_p
        
        if ev > 0.08: advice, a_class = "🔥 發現超額 Alpha (高價值)", "ev-positive"
        elif ev < -0.05: advice, a_class = "⚠️ 規避陷阱 (預期獲利為負)", "ev-negative"
        else: advice, a_class = "⏳ 觀望 (缺乏投注價值)", ""
        
        return {
            "p": [h_p, d_p, a_p], "o25": o25, "ev": ev, 
            "matrix": matrix, "fat_tail": fat_tail_prob,
            "advice": advice, "a_class": a_class
        }

# ==========================================
# 🏟️ 3. 賽事數據庫 (含文章提及的機器學習準確率概念)
# ==========================================
matches = [
    {
        "id": "1397", "league": "西甲 - 第 31 輪", "h": "赫塔菲", "a": "萊萬特", 
        "h_exp": 1.45, "a_exp": 1.15, "h_injury": False, "a_injury": True, "mkt_o": 2.15,
        "h_rank": "8 (主場第5)", "a_rank": "15 (客場第18)", 
        "h_form": "WWDWL", "a_form": "LLDLL",
        "formation": "5-4-1", "style": "防守反擊", "ml_conf": "54.55%"
    }
]

# ==========================================
# 🖥️ 4. 渲染執行
# ==========================================
st.markdown("<h1 style='text-align:center; color:#00ff88; font-weight:900;'>🛡️ MATCH PREDICT PRO v9.0</h1>", unsafe_allow_html=True)
st.caption("v9.0 已整合 Zero-Inflated Poisson 修正 (0:0校準) 與 Fat Tail (極端大分) 演算法。")

engine = QuantumDeepEngine()

for m in matches:
    res = engine.analyze(m)
    
    def get_form_html(form_str):
        return "".join([f'<span class="form-dot {s.lower()}">{s}</span>' for s in form_str])

    # 包含 0:0 與極端大分的全新波膽選單
    scores = [
        ("0:0 (悶平)", res['matrix'][0,0]), 
        ("1:0 (小勝)", res['matrix'][1,0]), 
        ("0:1 (冷門)", res['matrix'][0,1]), 
        ("1:1 (僵局)", res['matrix'][1,1]), 
        ("2:1 (主勝)", res['matrix'][2,1]),
        ("3+ 球 (極端大分)", res['fat_tail'])
    ]
    
    scores_html = "".join([f"""
        <div style="margin-bottom:12px;">
            <div class="score-row"><span style="color:#8b949e;">{label}</span><b style="color:#fff;">{prob:.1%}</b></div>
            <div class="bar-container"><div class="bar-fill" style="width:{prob*100*3}%; background:{'#ff4b4b' if label.startswith('0:0') else '#58a6ff'};"></div></div>
        </div>""" for label, prob in scores])

    card_html = f"""
    {PRO_STYLE}
    <div class="match-card">
        <div class="header">
            <div>
                <span class="league-info">{m['league']}</span>
                <div class="match-title">{m['h']} VS {m['a']}</div>
                <div style="margin-top:8px;">{get_form_html(m['h_form'])} <span style="color:#444; margin:0 10px;">vs</span> {get_form_html(m['a_form'])}</div>
            </div>
            <div class="ev-badge {res['a_class']}">{res['advice']}</div>
        </div>

        <div class="metric-grid">
            <div class="metric-box"><span class="info-label">DNN 歷史準確率</span><span class="data-val" style="color:#00ff88;">{m['ml_conf']}</span></div>
            <div class="metric-box"><span class="info-label">陣型風格</span><span class="data-val">{m['formation']} ({m['style']})</span></div>
            <div class="metric-box"><span class="info-label">期望盈利率 (EV)</span><span class="data-val" style="color:#f1c40f;">{res['ev']:.2%}</span></div>
            <div class="metric-box"><span class="info-label">傷停影響</span><span class="data-val">{"❌ 無" if not m['h_injury'] else "⚠️ 有"} / {"⚠️ 有" if m['a_injury'] else "❌ 無"}</span></div>
        </div>

        <div style="display:grid; grid-template-columns: 1.5fr 1fr; gap:30px; margin-top:20px;">
            <div>
                <span class="info-label">📊 核心機率 (已應用 Dixon-Coles 修正)</span>
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
                <span class="info-label">🎯 波膽能量條 (加入 0:0 與大分考量)</span>
                <div style="margin-top:10px;">{scores_html}</div>
            </div>
        </div>
    </div>
    """
    components.html(card_html, height=520, scrolling=False)
