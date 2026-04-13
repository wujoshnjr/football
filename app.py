import streamlit as st
import requests
import numpy as np
import math
import pytz
from datetime import datetime

# ==========================================
# 🔑 1. API 資源整合 (Secrets)
# ==========================================
S_KEYS = {
    "ODDS": st.secrets.get("ODDS_API_KEY"),
    "SPORTMONKS": st.secrets.get("SPORTMONKS_API_KEY"),
    "FOOTBALL_DATA": st.secrets.get("FOOTBALL_DATA_API_KEY"),
    "NEWS": st.secrets.get("NEWS_API_KEY"),
    "RAPID": st.secrets.get("RAPIDAPI_KEY")
}

# ==========================================
# 🎨 2. UI 樣式 (針對手機與台彩資訊優化)
# ==========================================
st.set_page_config(page_title="PREDICT PRO v23.0", layout="wide")

st.markdown("""
<style>
    .match-card {
        background: #161b22;
        border-radius: 12px;
        padding: 18px;
        margin-bottom: 15px;
        border-left: 10px solid #00ff88;
        border-right: 1px solid #30363d;
    }
    .recommend-badge {
        background: #f1c40f;
        color: #000;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: bold;
        font-size: 0.85rem;
    }
    .score-box {
        background: #0d1117;
        border: 1px solid #21262d;
        padding: 10px;
        border-radius: 8px;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 🧠 3. 核心運算：蒙地卡羅模擬 (含台彩玩法)
# ==========================================
def run_full_simulation(h_o, d_o, a_o, n_sims=100000):
    # Lambda 推算
    h_lambda = (1/h_o) * 2.75
    a_lambda = (1/a_o) * 2.75
    
    # 十萬次模擬
    h_sims = np.random.poisson(h_lambda, n_sims)
    a_sims = np.random.poisson(a_lambda, n_sims)
    
    # 基礎機率
    hp = np.sum(h_sims > a_sims) / n_sims
    dp = np.sum(h_sims == a_sims) / n_sims
    ap = np.sum(h_sims < a_sims) / n_sims
    
    # --- 台彩特色玩法計算 ---
    # 1. 大小分 (2.5球)
    total_goals = h_sims + a_sims
    over_25 = np.sum(total_goals > 2.5) / n_sims
    under_25 = 1 - over_25
    
    # 2. 讓分 (假設讓 1 球基準)
    # 讓主勝：主隊進球 - 1 > 客隊進球
    h_handicap_win = np.sum((h_sims - 1) > a_sims) / n_sims
    
    # 3. 推薦邏輯
    rec_list = []
    if over_25 > 0.60: rec_list.append("🔥 大分 2.5")
    if under_25 > 0.60: rec_list.append("❄️ 小分 2.5")
    if hp > 0.55: rec_list.append("🏠 主勝")
    elif ap > 0.55: rec_list.append("🚌 客勝")
    
    # 波膽
    results = [f"{h}:{a}" for h, a in zip(h_sims, a_sims)]
    unique, counts = np.unique(results, return_counts=True)
    top_scores = sorted(zip(unique, counts/n_sims), key=lambda x: x[1], reverse=True)[:5]
    
    return hp, dp, ap, over_25, h_handicap_win, rec_list, top_scores

# ==========================================
# 🖥️ 4. 主畫面渲染
# ==========================================
def main():
    st.markdown("<h1 style='text-align:center; color:#00ff88;'>🛡️ PREDICT PRO v23.0</h1>", unsafe_allow_html=True)
    
    url = f"https://api.the-odds-api.com/v4/sports/soccer/odds/?apiKey={S_KEYS['ODDS']}&regions=eu"
    try:
        res = requests.get(url).json()
    except:
        st.error("API 連線失敗")
        return

    if not res or "msg" in res:
        st.warning("目前無數據。")
        return

    for m in res:
        try:
            # 數據解析與模擬
            bookie = m['bookmakers'][0]['markets'][0]['outcomes']
            h_o = next(o['price'] for o in bookie if o['name'] == m['home_team'])
            d_o = next(o['price'] for o in bookie if o['name'] == 'Draw')
            a_o = next(o['price'] for o in bookie if o['name'] == m['away_team'])
            
            hp, dp, ap, ov, h_h, recs, scores = run_full_simulation(h_o, d_o, a_o)
            
            # 卡片頂部
            st.markdown(f"""
            <div class="match-card">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <span style="color:#8b949e; font-size:0.8rem;">{m['sport_title']}</span>
                    <div style="display:flex; gap:5px;">
                        {' '.join([f'<span class="recommend-badge">{r}</span>' for r in recs])}
                    </div>
                </div>
                <h2 style="margin:10px 0; color:white;">{m['home_team']} VS {m['away_team']}</h2>
            </div>
            """, unsafe_allow_html=True)

            tab1, tab2, tab3 = st.tabs(["📊 台彩玩法推薦", "🎯 模擬波膽", "📋 賽事情報"])
            
            with tab1:
                c1, c2 = st.columns(2)
                with c1:
                    st.write("**大小分 (2.5)**")
                    st.metric("大分機率", f"{ov:.1%}")
                    st.progress(ov)
                with c2:
                    st.write("**讓分 (讓1球)**")
                    st.metric("讓主勝率", f"{h_h:.1%}")
                    st.progress(h_h)
                
                st.divider()
                st.write("**主平客機率 (不讓分)**")
                k1, k2, k3 = st.columns(3)
                k1.metric("主勝", f"{hp:.1%}")
                k2.metric("和局", f"{dp:.1%}")
                k3.metric("客勝", f"{ap:.1%}")

            with tab2:
                st.write("🎲 **10萬次模擬最常出現比分：**")
                sc_cols = st.columns(5)
                for i, (s, p) in enumerate(scores):
                    sc_cols[i].markdown(f"<div class='score-box'><small>{s}</small><br><b style='color:#58a6ff;'>{p:.1%}</b></div>", unsafe_allow_html=True)

            with tab3:
                st.write(f"⏰ **開賽時間:** {m['commence_time']}")
                st.write(f"📈 **市場賠率:** 主 {h_o} / 平 {d_o} / 客 {a_o}")

            st.markdown("<br>", unsafe_allow_html=True)
        except:
            continue

if __name__ == "__main__":
    main()
