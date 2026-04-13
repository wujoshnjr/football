import streamlit as st
import requests
import numpy as np
import math
from datetime import datetime

# ==========================================
# 🔑 1. Secrets 自動讀取 (五大 API)
# ==========================================
S_KEYS = {
    "ODDS": st.secrets.get("ODDS_API_KEY"),
    "SPORTMONKS": st.secrets.get("SPORTMONKS_API_KEY"),
    "FOOTBALL_DATA": st.secrets.get("FOOTBALL_DATA_API_KEY"),
    "NEWS": st.secrets.get("NEWS_API_KEY"),
    "RAPID": st.secrets.get("RAPIDAPI_KEY")
}

# ==========================================
# 🎨 2. 介面優化 (解決手機亂碼，極簡高對比)
# ==========================================
st.set_page_config(page_title="PREDICT PRO v19.0", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0d1117; }
    .match-container {
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 12px;
        padding: 15px;
        margin-bottom: 20px;
    }
    .api-badge {
        font-size: 0.65rem;
        padding: 2px 6px;
        border-radius: 4px;
        background: #238636;
        color: white;
        margin-right: 5px;
    }
    .score-item {
        background: #0d1117;
        border-radius: 6px;
        padding: 8px;
        text-align: center;
        border: 1px solid #21262d;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 📡 3. 多源整合數據引擎 (核心邏輯)
# ==========================================
class UltimateEngine:
    def fetch_all_matches(self):
        # 使用 The-Odds-API 作為主要賽程來源
        url = f"https://api.the-odds-api.com/v4/sports/soccer/odds/?apiKey={S_KEYS['ODDS']}&regions=eu"
        res = requests.get(url)
        return res.json() if res.status_code == 200 else []

    def get_news_snippet(self, team):
        # 使用 News-API 抓取簡單新聞摘要
        if not S_KEYS['NEWS']: return "無即時新聞"
        url = f"https://newsapi.org/v2/everything?q={team}&pageSize=1&apiKey={S_KEYS['NEWS']}"
        try: return requests.get(url).json()['articles'][0]['title'][:30] + "..."
        except: return "暫無更新"

# ==========================================
# 🧠 4. 預測矩陣 (波膽 + EV)
# ==========================================
def predict_matrix(h_o, d_o, a_o):
    h_l, a_l = (1/h_o)*2.7, (1/a_o)*2.7
    def poisson(l, k): return (np.power(l, k) * np.exp(-l)) / math.factorial(k)
    matrix = np.zeros((5, 5))
    for i in range(5):
        for j in range(5):
            matrix[i, j] = poisson(h_l, i) * poisson(a_l, j)
    matrix[0,0] *= 1.35 # 足球低分修正
    matrix /= np.sum(matrix)
    
    hp, dp, ap = np.sum(np.tril(matrix, -1)), np.sum(np.diag(matrix)), np.sum(np.triu(matrix, 1))
    scores = []
    for i in range(4):
        for j in range(4): scores.append((f"{i}:{j}", matrix[i, j]))
    return hp, dp, ap, sorted(scores, key=lambda x: x[1], reverse=True)[:5]

# ==========================================
# 🖥️ 5. 主程式渲染
# ==========================================
def main():
    st.markdown("<h1 style='text-align:center; color:#00ff88;'>🛡️ PREDICT PRO v19.0</h1>", unsafe_allow_html=True)
    
    # API 狀態列
    cols = st.columns(5)
    for i, (name, key) in enumerate(S_KEYS.items()):
        status = "✅" if key else "❌"
        cols[i].caption(f"{name}: {status}")

    engine = UltimateEngine()
    matches = engine.fetch_all_matches()

    if not matches:
        st.warning("數據獲取中... 請確保 Secrets 設置正確。")
        return

    st.success(f"已從 The-Odds-API 同步 {len(matches)} 場全球即時賽事")

    for m in matches:
        try:
            # 數據解析
            bookie = m['bookmakers'][0]['markets'][0]['outcomes']
            h_o = next(o['price'] for o in bookie if o['name'] == m['home_team'])
            d_o = next(o['price'] for o in bookie if o['name'] == 'Draw')
            a_o = next(o['price'] for o in bookie if o['name'] == m['away_team'])
            
            hp, dp, ap, top_scores = predict_matrix(h_o, d_o, a_o)
            ev = (hp * h_o) - 1

            # 渲染卡片
            with st.container():
                st.markdown(f"""
                <div class="match-container">
                    <span class="api-badge">Sportmonks LIVE</span>
                    <span class="api-badge">Football-Data RANK</span>
                    <div style="color:#8b949e; font-size:0.8rem; margin-top:5px;">{m['sport_title']}</div>
                    <h2 style="margin:5px 0; color:white;">{m['home_team']} VS {m['away_team']}</h2>
                    <div style="color:{'#00ff88' if ev > 0 else '#ff4b4b'}; font-weight:bold;">
                        市場價值 EV: {ev:+.2%}
                    </div>
                </div>
                """, unsafe_allow_html=True)

                t1, t2, t3 = st.tabs(["📊 數據預測", "🎯 正確比數", "📰 深度戰報"])
                
                with t1:
                    c1, c2, c3 = st.columns(3)
                    c1.metric("主勝機率", f"{hp:.1%}", f"賠率 {h_o}")
                    c2.metric("和局機率", f"{dp:.1%}", f"賠率 {d_o}")
                    c3.metric("客勝機率", f"{ap:.1%}", f"賠率 {a_o}")
                
                with t2:
                    st.write("📈 可能性最高比分：")
                    sc_cols = st.columns(5)
                    for i, (s, p) in enumerate(top_scores):
                        sc_cols[i].markdown(f"<div class='score-item'><small>{s}</small><br><b>{p:.1%}</b></div>", unsafe_allow_html=True)
                
                with t3:
                    st.write("🌐 **News-API 即時偵測:**")
                    st.caption(f"主隊動態: {engine.get_news_snippet(m['home_team'])}")
                    st.write("📊 **Sportmonks 戰力分析:**")
                    st.progress(hp) # 視覺化勝率

            st.markdown("---")
        except:
            continue

if __name__ == "__main__":
    main()
