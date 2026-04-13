import streamlit as st
import requests
import numpy as np
import pandas as pd
from datetime import datetime

# ==========================================
# 🔑 1. 全球聯賽戰術特徵庫
# ==========================================
LEAGUE_BIAS = {
    "Premier League": {"adj": 1.12, "style": "高強度對抗/大分傾向", "label": "🔥 攻勢足球"},
    "La Liga": {"adj": 0.98, "style": "細膩控球/技術型踢法", "label": "🪄 技術足球"},
    "Serie A": {"adj": 0.92, "style": "傳統鏈式防守/小分傾向", "label": "🛡️ 戰術防守"},
    "Bundesliga": {"adj": 1.28, "style": "高位壓迫/極大分傾向", "label": "🏹 激情全攻"},
    "Premier League - Russia": {"adj": 0.82, "style": "硬朗防守/低進球模式", "label": "❄️ 鐵血防守"},
    "Ligue 1": {"adj": 1.05, "style": "體能化對抗/中性進球", "label": "🏃 強力對抗"}
}

# ==========================================
# 🎨 2. UI 視覺配置
# ==========================================
st.set_page_config(page_title="ZEUS PRO v41.0", layout="wide")
st.markdown("""
<style>
    .stApp { background-color: #0d1117; color: #e6edf3; }
    .master-card {
        background: #161b22; border: 1px solid #30363d; border-radius: 16px;
        padding: 24px; margin-bottom: 22px; border-left: 12px solid #00ff88;
    }
    .home-tag { background: #238636; color: white; padding: 3px 10px; border-radius: 6px; font-weight: bold; }
    .away-tag { background: #1f6feb; color: white; padding: 3px 10px; border-radius: 6px; font-weight: bold; }
    .rec-badge { background: #f1c40f; color: #000; padding: 6px 14px; border-radius: 8px; font-weight: 900; }
    .edge-val { color: #00ff88; font-weight: 800; font-size: 1.1rem; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 🧠 3. 核心模擬引擎 (全域適配版)
# ==========================================
def run_simulation_v41(h_o, d_o, a_o, league_name, n_sims=100000):
    # 如果聯賽不在清單內，使用 1.0 標準值
    bias = LEAGUE_BIAS.get(league_name, {"adj": 1.0, "style": "標準足球數據", "label": "📊 常規診斷"})
    h_l = (1/h_o) * 2.80 * bias['adj']
    a_l = (1/a_o) * 2.80 * bias['adj']
    
    h_s = np.random.poisson(h_l, n_sims)
    a_s = np.random.poisson(a_l, n_sims)
    
    hp, dp, ap = np.sum(h_s > a_s)/n_sims, np.sum(h_s == a_s)/n_sims, np.sum(h_s < a_s)/n_sims
    ov25 = np.sum((h_s + a_s) > 2.5)/n_sims
    he, de, ae = hp - (1/h_o), dp - (1/d_o), ap - (1/a_o)
    
    recs = []
    if he > 0.045: recs.append("🏠 不讓分主推")
    if ae > 0.045: recs.append("🚀 不讓分客推")
    if de > 0.05: recs.append("💎 和局博弈")
    if ov25 > 0.62: recs.append("🔥 大分 2.5")
    if ov25 < 0.36: recs.append("🛡️ 小分 2.5")
    
    return hp, dp, ap, ov25, he, de, ae, bias

# ==========================================
# 🖥️ 4. 實戰主流程
# ==========================================
def main():
    st.markdown("<h1 style='text-align:center; color:#00ff88;'>🛡️ ZEUS PREDICT PRO v41.0</h1>", unsafe_allow_html=True)
    curr_time = datetime.now().strftime('%H:%M:%S')
    st.caption(f"🚀 最後更新：{curr_time} | 數據模式：全域觀測自動開啟")

    # API 請求
    API_URL = f"https://api.the-odds-api.com/v4/sports/soccer/odds/?apiKey={st.secrets['ODDS_API_KEY']}&regions=eu&markets=h2h"
    try:
        response = requests.get(API_URL)
        data = response.json()
    except Exception as e:
        st.error(f"❌ API 連線異常: {str(e)}")
        return

    # 針對「沒有比賽」的修正提示
    if not data:
        st.warning("⚠️ 目前 API 沒有回傳任何比賽數據。")
        st.info("常見原因：1.當前時段無大型比賽 2.API Key 額度已用盡 3.伺服器維護中。")
        return

    tab_main, tab_info = st.tabs(["🎯 實戰預測中心", "⚙️ 系統診斷"])

    with tab_main:
        for m in data[:25]: # 增加顯示數量至 25 場
            try:
                # 獲取賠率
                market = m['bookmakers'][0]['markets'][0]['outcomes']
                h_o = next(o['price'] for o in market if o['name'] == m['home_team'])
                d_o = next(o['price'] for o in market if o['name'] == 'Draw')
                a_o = next(o['price'] for o in market if o['name'] == m['away_team'])
                
                hp, dp, ap, ov, he, de, ae, bias = run_simulation_v41(h_o, d_o, a_o, m['sport_title'])

                st.markdown(f"""
                <div class="master-card">
                    <div style="display:flex; justify-content:space-between;">
                        <span style="color:#8b949e; font-size:0.85rem;">🏆 {m['sport_title']} | {bias['label']}</span>
                        <span class="edge-val">優勢 Edge: {max(he, ae, de):+.1%}</span>
                    </div>
                    <div style="margin: 18px 0;">
                        <span class="home-tag">主</span> <b style="font-size:1.3rem; color:white;">{m['home_team']}</b>
                        <br><span style="color:#58a6ff; font-weight:bold; margin-left:35px;">VS</span><br>
                        <span class="away-tag">客</span> <b style="font-size:1.3rem; color:white;">{m['away_team']}</b>
                    </div>
                    <div style="display:flex; flex-wrap:wrap; gap:10px;">
                        {' '.join([f'<span class="rec-badge">{r}</span>' for r in recs]) if recs else '<span style="color:#8b949e;">模型觀望中...</span>'}
                    </div>
                </div>
                """, unsafe_allow_html=True)

                with st.expander("📝 深度診斷報告 (不讓分與戰術分析)"):
                    c1, c2 = st.columns(2)
                    with c1:
                        st.write("**🎲 不讓分預測**")
                        st.write(f"主勝: {hp:.1%} | 客勝: {ap:.1%} | 和局: {dp:.1%}")
                    with c2:
                        st.write("**⚽ 進球模式**")
                        st.write(f"大分 2.5 機率: {ov:.1%}")
                        st.write(f"踢法: {bias['style']}")
                st.divider()
            except: continue

    with tab_info:
        st.subheader("⚙️ 聯賽適配列表")
        st.write("已針對以下聯賽進行 Lambda 自動優化，其餘聯賽以標準 1.0 運行。")
        st.table(pd.DataFrame([{"聯賽": k, "風格": v['style']} for k, v in LEAGUE_BIAS.items()]))

if __name__ == "__main__":
    main()
