import streamlit as st
import requests
import numpy as np
import math
from datetime import datetime

# ==========================================
# 🔑 1. API 密鑰配置 (請填入你手邊有的 Key)
# ==========================================
ODDS_API_KEY = "你的_ODDS_API_KEY"
SPORTMONKS_API_KEY = "你的_SPORTMONKS_KEY"

# ==========================================
# 🎨 2. UI 強度優化 (高清晰度、多賽事卡片)
# ==========================================
st.set_page_config(page_title="Match Predict Pro v16.0", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0d1117; color: #c9d1d9; }
    .match-container {
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 25px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.5);
    }
    .status-bar { display: flex; justify-content: space-between; margin-bottom: 10px; font-size: 0.8rem; }
    .league-tag { color: #58a6ff; font-weight: bold; }
    .ev-tag { background: #238636; color: #fff; padding: 2px 6px; border-radius: 4px; font-weight: bold; }
    .score-item { 
        background: #0d1117; border: 1px solid #21262d; border-radius: 6px; 
        padding: 10px; text-align: center; color: #58a6ff; font-family: 'JetBrains Mono', monospace;
    }
    h2 { color: #ffffff !important; margin: 5px 0 !important; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 📡 3. 數據抓取引擎
# ==========================================
def get_global_matches():
    """使用 The-Odds-API 抓取全球賽事"""
    url = f"https://api.the-odds-api.com/v4/sports/soccer/odds/?apiKey={ODDS_API_KEY}&regions=eu&markets=h2h"
    try:
        res = requests.get(url)
        return res.json() if res.status_code == 200 else []
    except:
        return []

# ==========================================
# 🧠 4. 模型核心 (Dixon-Coles 修正)
# ==========================================
def analyze_match(h_o, d_o, a_o):
    # 基於賠率與統計係數推算 Lambda
    h_l = (1/h_o) * 2.7
    a_l = (1/a_o) * 2.7
    
    def poisson(l, k): return (np.power(l, k) * np.exp(-l)) / math.factorial(k)
    
    matrix = np.zeros((6, 6))
    for i in range(6):
        for j in range(6):
            matrix[i, j] = poisson(h_l, i) * poisson(a_l, j)
    
    # Dixon-Coles 0:0 零膨脹修正
    matrix[0,0] *= 1.35
    matrix /= np.sum(matrix)
    
    hp = np.sum(np.tril(matrix, -1))
    dp = np.sum(np.diag(matrix))
    ap = np.sum(np.triu(matrix, 1))
    
    # 提取 Top 5 波膽
    scores = []
    for i in range(4):
        for j in range(4):
            scores.append((f"{i}:{j}", matrix[i, j]))
    top_scores = sorted(scores, key=lambda x: x[1], reverse=True)[:5]
    
    return hp, dp, ap, top_scores

# ==========================================
# 🖥️ 5. 畫面渲染
# ==========================================
def main():
    st.markdown("<h1 style='text-align:center; color:#00ff88;'>🛡️ MATCH PREDICT PRO v16.0</h1>", unsafe_allow_html=True)
    st.write(f"🔄 **本地端運行模式** | 同步時間: {datetime.now().strftime('%H:%M:%S')}")

    matches = get_global_matches()
    
    if not matches:
        st.error("❌ 無法抓取數據，請確認 API Key。")
        return

    st.success(f"✅ 已抓取當前全球賽事: {len(matches)} 場")

    for m in matches:
        try:
            # 解析賠率
            bookie = m['bookmakers'][0]['markets'][0]['outcomes']
            h_o = next(x['price'] for x in bookie if x['name'] == m['home_team'])
            d_o = next(x['price'] for x in bookie if x['name'] == 'Draw')
            a_o = next(x['price'] for x in bookie if x['name'] == m['away_team'])
            
            hp, dp, ap, scores = analyze_match(h_o, d_o, a_o)
            ev = (hp * h_o) - 1

            # 渲染卡片
            st.markdown(f"""
            <div class="match-container">
                <div class="status-bar">
                    <span class="league-tag">{m['sport_title']}</span>
                    <span class="ev-tag">EV: {ev:+.2%}</span>
                </div>
                <h2>{m['home_team']} VS {m['away_team']}</h2>
            </div>
            """, unsafe_allow_html=True)

            # 使用 Tabs 區分內容，解決版面雜亂
            t1, t2, t3 = st.tabs(["📊 賠率機率分析", "🎯 正確比數 (波膽)", "📋 深度統計"])
            
            with t1:
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("模型勝率", f"{hp:.1%}")
                c2.metric("和局機率", f"{dp:.1%}")
                c3.metric("市場賠率", f"{h_o:.2f}")
                c4.metric("價值評估", "✅ 高" if ev > 0.05 else "⚠️ 中")
            
            with t2:
                st.write("📈 **可能性最高的五個比分：**")
                sc_cols = st.columns(5)
                for idx, (s, p) in enumerate(scores):
                    sc_cols[idx].markdown(f"""
                    <div class="score-item">
                        <span style="font-size:0.75rem; color:#8b949e;">{s}</span><br>
                        <b>{p:.1%}</b>
                    </div>
                    """, unsafe_allow_html=True)

            with t3:
                st.write("⚙️ **多源 API 串接狀態**")
                st.json({
                    "Odds_Source": "The Odds API",
                    "Stats_Source": "Sportmonks (Pending)",
                    "Match_ID": m['id']
                })
            
            st.markdown("<br>", unsafe_allow_html=True)

        except:
            continue

if __name__ == "__main__":
    main()
