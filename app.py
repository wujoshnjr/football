import streamlit as st
import requests
import numpy as np
import math
from datetime import datetime

# ==========================================
# 🔑 1. 從 Streamlit Secrets 讀取 Key
# ==========================================
# 請確保在 .streamlit/secrets.toml 裡有 ODDS_API_KEY
try:
    API_KEY = st.secrets["ODDS_API_KEY"]
except:
    st.error("❌ 未在 Secrets 中找到 ODDS_API_KEY，請檢查配置。")
    st.stop()

# ==========================================
# 🎨 2. UI 佈置 (高對比度、手機優化)
# ==========================================
st.set_page_config(page_title="Match Predict Pro v18.0", layout="wide")

st.markdown("""
<style>
    .match-header {
        background: #161b22;
        padding: 15px;
        border-radius: 10px;
        border-left: 6px solid #00ff88;
        margin-bottom: 5px;
    }
    .league-name { color: #58a6ff; font-weight: bold; font-size: 0.8rem; }
    .score-card {
        background: #0d1117;
        border: 1px solid #30363d;
        padding: 12px;
        border-radius: 8px;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 🧠 3. 預測邏輯 (波膽矩陣)
# ==========================================
def calculate_predictions(h_o, d_o, a_o):
    # 賠率反推 Lambda (期望進球)
    h_l, a_l = (1/h_o)*2.75, (1/a_o)*2.75
    
    def poisson(l, k): return (np.power(l, k) * np.exp(-l)) / math.factorial(k)
    
    matrix = np.zeros((5, 5))
    for i in range(5):
        for j in range(5):
            matrix[i, j] = poisson(h_l, i) * poisson(a_l, j)
    
    # Dixon-Coles 修正
    matrix[0,0] *= 1.35
    matrix /= np.sum(matrix)
    
    h_p = np.sum(np.tril(matrix, -1))
    d_p = np.sum(np.diag(matrix))
    a_p = np.sum(np.triu(matrix, 1))
    
    scores = []
    for i in range(4):
        for j in range(4):
            scores.append((f"{i}:{j}", matrix[i, j]))
    
    return h_p, d_p, a_p, sorted(scores, key=lambda x: x[1], reverse=True)[:5]

# ==========================================
# 🖥️ 4. 主程式渲染 (全自動循環)
# ==========================================
def main():
    st.markdown("<h1 style='text-align:center; color:#00ff88;'>🛡️ PREDICT PRO v18.0</h1>", unsafe_allow_html=True)
    st.write(f"📡 **數據源：The-Odds-API** | 同步時間: {datetime.now().strftime('%H:%M:%S')}")

    # 抓取全球足球賽事 (soccer)
    url = f"https://api.the-odds-api.com/v4/sports/soccer/odds/?apiKey={API_KEY}&regions=eu&markets=h2h"
    
    with st.spinner('正在同步全球賽事數據...'):
        try:
            res = requests.get(url)
            matches = res.json()
        except:
            st.error("連線 API 失敗")
            return

    if not matches or "msg" in matches:
        st.warning("目前沒有賽事數據，或 API Key 額度已達上限。")
        return

    st.success(f"✅ 已成功抓取今日共 **{len(matches)}** 場足球賽事")

    # --- 自動循環生成卡片 ---
    for m in matches:
        try:
            # 解析主平客賠率
            bookie = m['bookmakers'][0]['markets'][0]['outcomes']
            h_o = next(o['price'] for o in bookie if o['name'] == m['home_team'])
            d_o = next(o['price'] for o in bookie if o['name'] == 'Draw')
            a_o = next(o['price'] for o in bookie if o['name'] == m['away_team'])
            
            hp, dp, ap, top_scores = calculate_predictions(h_o, d_o, a_o)
            ev = (hp * h_o) - 1

            # 渲染 UI 卡片
            st.markdown(f"""
            <div class="match-header">
                <div class="league-name">{m['sport_title']}</div>
                <h3 style="margin:0; color:white;">{m['home_team']} VS {m['away_team']}</h3>
            </div>
            """, unsafe_allow_html=True)

            tab1, tab2 = st.tabs(["📊 數據預測", "🎯 正確比數 (波膽)"])
            
            with tab1:
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("主勝機率", f"{hp:.1%}", f"賠率 {h_o}")
                c2.metric("模型和局", f"{dp:.1%}")
                c3.metric("客勝機率", f"{ap:.1%}", f"賠率 {a_o}")
                c4.metric("市場 EV", f"{ev:.2%}", delta=f"{ev:.2%}")

            with tab2:
                sc_cols = st.columns(5)
                for i, (s, p) in enumerate(top_scores):
                    sc_cols[i].markdown(f"""
                    <div class="score-card">
                        <span style="font-size:0.7rem; color:#8b949e;">{s}</span><br>
                        <b style="color:#58a6ff;">{p:.1%}</b>
                    </div>
                    """, unsafe_allow_html=True)
            
            st.markdown("<br>", unsafe_allow_html=True)

        except Exception:
            continue # 跳過資料不齊全的比賽

if __name__ == "__main__":
    main()
