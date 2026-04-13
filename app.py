import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# ==========================================
# 🎨 1. 專業交易 UI 配置 (整合台彩元素)
# ==========================================
st.set_page_config(page_title="MATCH PREDICT PRO v6.8", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #05070a; color: #e0e0e0; }
    .main-header { font-size: 2.2rem; color: #00ff88; font-weight: 800; text-align: center; margin-bottom: 20px; }
    .pro-card { background: #0d1117; border: 1px solid #30363d; border-radius: 12px; padding: 20px; margin-bottom: 15px; }
    .info-label { color: #888; font-size: 0.8rem; }
    .data-val { font-weight: bold; color: #fff; }
    .h2h-win { color: #00ff88; } .h2h-draw { color: #888; } .h2h-loss { color: #ff4b4b; }
    .form-w { color: #00ff88; margin-right: 2px; } .form-d { color: #888; margin-right: 2px; } .form-l { color: #ff4b4b; margin-right: 2px; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 🧠 2. 模擬引擎與數據模擬 (對標台彩資訊)
# ==========================================
class QuantumEngine:
    def get_odds_history(self):
        times = pd.date_range(start=datetime.now() - timedelta(hours=23), periods=24, freq='h')
        odds = [2.25]
        for _ in range(23): odds.append(odds[-1] + np.random.uniform(-0.04, 0.04))
        return pd.DataFrame({"Time": times, "Odds": odds})

    def run_simulation(self, m):
        # 模擬決策建議
        h_p = np.random.uniform(0.40, 0.60)
        mkt_p = 1 / m['mkt_o']
        ev = h_p - mkt_p
        action = "🎯 建議下注" if ev > 0.05 else "⛔ 誘盤警告" if ev < -0.05 else "⏳ 觀望"
        return {"h_p": h_p, "ev": ev, "action": action}

# ==========================================
# 🏟️ 3. 主介面渲染
# ==========================================
st.markdown('<div class="main-header">🛡️ MATCH PREDICT PRO v6.8</div>', unsafe_allow_html=True)
engine = QuantumEngine()

# 模擬比賽數據集 (對標截圖中的 赫塔菲 vs 萊萬特)
matches = [
    {
        "h": "Getafe", "a": "Levante", "mkt_o": 2.30, "league": "La Liga",
        "h_rank": 8, "a_rank": 15,
        "h2h": {"w": 1, "d": 3, "l": 1},
        "h_form": ["W", "D", "L", "W", "D"],
        "a_form": ["L", "L", "D", "L", "W"],
        "h_goals": {"scored": 0.9, "conceded": 1.0},
        "a_goals": {"scored": 1.1, "conceded": 1.7},
        "formation": "5-4-1 vs 4-2-3-1"
    }
]

left_col, right_col = st.columns([1.8, 1.2])

with left_col:
    st.subheader("⚡ 實時競爭力分析 (含基本面數據)")
    
    for m in matches:
        sim = engine.run_simulation(m)
        
        with st.container():
            st.markdown(f"""
            <div class="pro-card">
                <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #30363d; padding-bottom:10px; margin-bottom:15px;">
                    <div>
                        <span style="color:#f1c40f; font-weight:bold;">{m['league']}</span><br>
                        <b style="font-size:1.4rem;">{m['h']} <span style="color:#ff4b4b;">VS</span> {m['a']}</b>
                    </div>
                    <div style="background:rgba(0,255,136,0.1); border:1px solid #00ff88; padding:5px 15px; border-radius:20px; color:#00ff88;">
                        {sim['action']}
                    </div>
                </div>

                <div style="display:grid; grid-template-columns: 1fr 1fr 1fr; gap:10px; margin-bottom:15px; text-align:center;">
                    <div>
                        <span class="info-label">聯賽排名</span><br>
                        <span class="data-val">#{m['h_rank']} vs #{m['a_rank']}</span>
                    </div>
                    <div>
                        <span class="info-label">歷史對戰 (近5場)</span><br>
                        <span class="h2h-win">{m['h2h']['w']}勝</span> 
                        <span class="h2h-draw">{m['h2h']['d']}和</span> 
                        <span class="h2h-loss">{m['h2h']['l']}負</span>
                    </div>
                    <div>
                        <span class="info-label">預計陣型</span><br>
                        <span class="data-val">{m['formation']}</span>
                    </div>
                </div>

                <div style="display:grid; grid-template-columns: 1fr 1fr; gap:20px; margin-bottom:15px; background:rgba(255,255,255,0.02); padding:10px; border-radius:8px;">
                    <div style="text-align:center; border-right:1px solid #333;">
                        <span class="info-label">{m['h']} 場均進/失</span><br>
                        <span style="color:#00ff88;">{m['h_goals']['scored']}</span> / <span style="color:#ff4b4b;">{m['h_goals']['conceded']}</span>
                    </div>
                    <div style="text-align:center;">
                        <span class="info-label">{m['a']} 場均進/失</span><br>
                        <span style="color:#00ff88;">{m['a_goals']['scored']}</span> / <span style="color:#ff4b4b;">{m['a_goals']['conceded']}</span>
                    </div>
                </div>

                <div style="display:grid; grid-template-columns: repeat(3, 1fr); gap:10px; text-align:center; padding-top:10px;">
                    <div style="background:#161b22; padding:10px; border-radius:8px;">
                        <span class="info-label">模型預測勝率</span><br>
                        <b style="color:#00ff88; font-size:1.2rem;">{sim['h_p']:.1%}</b>
                    </div>
                    <div style="background:#161b22; padding:10px; border-radius:8px;">
                        <span class="info-label">市場 EV</span><br>
                        <b style="color:#f1c40f; font-size:1.2rem;">{sim['ev']:.2%}</b>
                    </div>
                    <div style="background:#161b22; padding:10px; border-radius:8px;">
                        <span class="info-label">市場賠率</span><br>
                        <b style="font-size:1.2rem;">{m['mkt_o']}</b>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

with right_col:
    st.subheader("📈 市場數據走向")
    df_odds = engine.get_odds_history()
    st.line_chart(df_odds.set_index("Time"), color="#00ff88")
    
    st.markdown("""
    <div class="pro-card">
        <b style="color:#00ff88;">🧠 AI 綜合診斷：</b><br>
        <p style="font-size:0.85rem; color:#ccc; margin-top:8px;">
        1. <b>排名優勢：</b>赫塔菲排名第 8，遠高於萊萬特的第 15。<br>
        2. <b>防守穩定：</b>主隊場均失球僅 1.0，對比萊萬特的 1.7 有顯著優勢。<br>
        3. <b>H2H 趨勢：</b>兩隊歷史交鋒多平局（3場），需警惕平盤風險。<br>
        4. <b>結論：</b>模型 $\lambda$ 修正後支持主勝，配合賠率下行趨勢，建議主勝或主讓。
        </p>
    </div>
    """, unsafe_allow_html=True)
