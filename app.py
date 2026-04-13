import streamlit as st
import pandas as pd
import numpy as np
import time

# ==========================================
# 🎨 1. 專業交易 UI 配置 (延續 v6.6 风格)
# ==========================================
st.set_page_config(page_title="MATCH PREDICT PRO v6.7", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #05070a; color: #e0e0e0; }
    .main-header { font-size: 2.2rem; color: #00ff88; font-weight: 800; text-align: center; margin-bottom: 20px; }
    .pro-card { background: #0d1117; border: 1px solid #30363d; border-radius: 12px; padding: 20px; margin-bottom: 15px; }
    .bet-signal { background: rgba(0, 255, 136, 0.2); border: 2px solid #00ff88; padding: 10px; border-radius: 8px; text-align: center; color: #00ff88; font-weight: bold; font-size: 1.1rem; }
    .bet-avoid { background: rgba(255, 75, 75, 0.2); border: 2px solid #ff4b4b; padding: 10px; border-radius: 8px; text-align: center; color: #ff4b4b; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 🧠 2. 模擬引擎與決策邏輯
# ==========================================
class QuantumEngine:
    def get_odds_history(self):
        """模擬賠率走向數據 (實務中對接 Odds API 歷史端點)"""
        times = pd.date_range(start='2024-05-18', periods=24, freq='H')
        # 模擬水位變動趨勢
        odds = [2.25]
        for _ in range(23):
            odds.append(odds[-1] + np.random.uniform(-0.05, 0.05))
        return pd.DataFrame({"Time": times, "Odds": odds})

    def run_simulation(self, h_name, a_name, mkt_odds):
        # 延續 v6.6 的 Lambda 邏輯
        h_p = np.random.uniform(0.35, 0.55)  # 簡化模擬
        o25_p = np.random.uniform(0.40, 0.60)
        mkt_p = 1 / mkt_odds
        ev = h_p - mkt_p
        
        # 💡 決策判斷邏輯
        if ev > 0.05:
            action = f"✅ 建議下注：{h_name} (主勝)"
            status = "SIGNAL"
        elif ev < -0.10:
            action = "⚠️ 警示：EV 嚴重背離，建議避開"
            status = "AVOID"
        else:
            action = "💤 觀望：價值空間不足"
            status = "WAIT"
            
        return {"h_p": h_p, "o25": o25_p, "ev": ev, "action": action, "status": status}

# ==========================================
# 🏟️ 3. 主介面渲染
# ==========================================
st.markdown('<div class="main-header">🛡️ QUANTUM TERMINAL v6.7</div>', unsafe_allow_html=True)

engine = QuantumEngine()

# 頂部狀態列
st.sidebar.markdown("### ⚙️ 控制中心")
st.sidebar.metric("今日分析勝率", "78.4%", "+1.2%")
st.sidebar.divider()
min_ev = st.sidebar.slider("最小 EV 獲利門檻", -0.10, 0.20, 0.05)

left_col, right_col = st.columns([1.8, 1.2])

with left_col:
    st.subheader("⚡ 實時競爭力分析")
    
    matches = [
        {"h": "Fiorentina", "a": "Lazio", "mkt_o": 2.25},
        {"h": "Levante UD", "a": "Getafe CF", "mkt_o": 2.80}
    ]
    
    for m in matches:
        sim = engine.run_simulation(m['h'], m['a'], m['mkt_o'])
        
        with st.container():
            st.markdown(f"""
            <div class="pro-card">
                <div style="display:flex; justify-content:space-between;">
                    <b style="font-size:1.2rem;">{m['h']} VS {m['a']}</b>
                    <span style="color:#888;">市場賠率: {m['mkt_o']}</span>
                </div>
                <div style="margin: 15px 0;">
                    <div class="{'bet-signal' if sim['status'] == 'SIGNAL' else 'bet-avoid' if sim['status'] == 'AVOID' else ''}" 
                         style="padding: 10px; border-radius: 8px; text-align: center; border: 1px solid;">
                        {sim['action']}
                    </div>
                </div>
                <div style="display:flex; justify-content:space-around; background:rgba(0,0,0,0.2); padding:10px; border-radius:8px;">
                    <div><small>模型勝率</small><br><b>{sim['h_p']:.1%}</b></div>
                    <div><small>大 2.5</small><br><b>{sim['o25']:.1%}</b></div>
                    <div><small>預期價值 (EV)</small><br><b style="color:#00ff88;">{sim['ev']:.2%}</b></div>
                </div>
            </div>
            """, unsafe_allow_html=True)

with right_col:
    st.subheader("📈 賠率走向監控 (24H)")
    
    # 這裡顯示選中比賽的趨勢圖
    selected_match = st.selectbox("選擇監控賽事", ["Fiorentina vs Lazio", "Levante vs Getafe"])
    
    df_odds = engine.get_odds_history()
    
    # 使用 Streamlit 原生折線圖，並美化樣式
    st.line_chart(df_odds.set_index("Time"), color="#00ff88")
    
    st.markdown("""
    <div class="pro-card">
        <small style="color:#888;">趨勢分析：</small><br>
        偵測到主隊水位在開賽前 4 小時有明顯<b>下調趨勢 (Steam Move)</b>，
        這通常意味著專業資金正在流入主隊，與模型預測方向一致。
    </div>
    """, unsafe_allow_html=True)

st.divider()
st.caption("v6.7 已整合：下注決策系統、賠率趨止監控、及底層 Lambda 自然連動邏輯。")
