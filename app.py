import streamlit as st
import requests
import numpy as np
import pandas as pd
from datetime import datetime

# ==========================================
# 🔑 1. 全球聯賽戰術特徵庫
# ==========================================
# 根據各聯賽踢法特徵調校 Lambda 期望值
LEAGUE_BIAS = {
    "Premier League": {"adj": 1.12, "style": "高強度對抗/大分傾向", "label": "🔥 攻勢足球"},
    "La Liga": {"adj": 0.98, "style": "細膩控球/技術型踢法", "label": "🪄 技術足球"},
    "Serie A": {"adj": 0.92, "style": "傳統鏈式防守/小分傾向", "label": "🛡️ 戰術防守"},
    "Bundesliga": {"adj": 1.28, "style": "高位壓迫/極大分傾向", "label": "🏹 激情全攻"},
    "Premier League - Russia": {"adj": 0.82, "style": "硬朗防守/低進球模式", "label": "❄️ 鐵血防守"},
    "Ligue 1": {"adj": 1.05, "style": "體能化對抗/中性進球", "label": "🏃 強力對抗"}
}

# ==========================================
# 🎨 2. 旗艦版視覺介面配置
# ==========================================
st.set_page_config(page_title="ZEUS PRO v40.0", layout="wide")
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
# 🧠 3. 核心模擬引擎 (戰術微調版)
# ==========================================
def run_simulation_v40(h_o, d_o, a_o, league_name, n_sims=100000):
    # 聯賽特徵調校核心
    bias = LEAGUE_BIAS.get(league_name, {"adj": 1.0, "style": "數據標準型", "label": "📊 標準分析"})
    h_l = (1/h_o) * 2.80 * bias['adj']
    a_l = (1/a_o) * 2.80 * bias['adj']
    
    # 蒙地卡羅模擬
    h_s = np.random.poisson(h_l, n_sims)
    a_s = np.random.poisson(a_l, n_sims)
    
    # 計算各玩法機率與 Edge
    hp, dp, ap = np.sum(h_s > a_s)/n_sims, np.sum(h_s == a_s)/n_sims, np.sum(h_s < a_s)/n_sims
    ov25 = np.sum((h_s + a_s) > 2.5)/n_sims
    he, de, ae = hp - (1/h_o), dp - (1/d_o), ap - (1/a_o)
    
    # 推薦邏輯標籤
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
    st.markdown("<h1 style='text-align:center; color:#00ff88;'>🛡️ ZEUS PREDICT PRO v40.0</h1>", unsafe_allow_html=True)
    st.caption(f"🚀 即時更新：{datetime.now().strftime('%H:%M:%S')} | 全球數據頻率：60s")

    # 抓取 API 數據 (需確保 Secrets 中已填寫關鍵字)
    API_URL = f"https://api.the-odds-api.com/v4/sports/soccer/odds/?apiKey={st.secrets['ODDS_API_KEY']}&regions=eu&markets=h2h"
    try:
        data = requests.get(API_URL).json()
    except:
        st.error("❌ API 連線中斷，請確認 API Key 是否有效。")
        return

    tab_active, tab_tactics = st.tabs(["🎯 實戰預測中心", "⚙️ 聯賽診斷庫"])

    with tab_active:
        for m in data[:20]:
            try:
                # 取得勝平負賠率
                market = m['bookmakers'][0]['markets'][0]['outcomes']
                h_o = next(o['price'] for o in market if o['name'] == m['home_team'])
                d_o = next(o['price'] for o in market if o['name'] == 'Draw')
                a_o = next(o['price'] for o in market if o['name'] == m['away_team'])
                
                # 執行模擬
                hp, dp, ap, ov, he, de, ae, bias = run_simulation_v40(h_o, d_o, a_o, m['sport_title'])

                # 渲染美化卡片
                st.markdown(f"""
                <div class="master-card">
                    <div style="display:flex; justify-content:space-between;">
                        <span style="color:#8b949e; font-size:0.85rem;">🏆 {m['sport_title']} | {bias['label']}</span>
                        <span class="edge-val">最高優勢: {max(he, ae, de):+.1%}</span>
                    </div>
                    <div style="margin: 18px 0;">
                        <span class="home-tag">主</span> <b style="font-size:1.3rem; color:white;">{m['home_team']}</b>
                        <br><span style="color:#58a6ff; font-weight:bold; margin-left:35px;">VS</span><br>
                        <span class="away-tag">客</span> <b style="font-size:1.3rem; color:white;">{m['away_team']}</b>
                    </div>
                    <div style="display:flex; flex-wrap:wrap; gap:10px;">
                        {' '.join([f'<span class="rec-badge">{r}</span>' for r in recs]) if recs else '<span style="color:#8b949e;">數據盤整中，建議觀望</span>'}
                    </div>
                </div>
                """, unsafe_allow_html=True)

                with st.expander("📝 深度戰術報告 (不讓分與踢法剖析)"):
                    c1, c2 = st.columns(2)
                    with c1:
                        st.write("**🎲 不讓分預測 (Win-Draw-Win)**")
                        st.write(f"主勝: **{hp:.1%}** (Edge: {he:+.1%})")
                        st.write(f"客勝: **{ap:.1%}** (Edge: {ae:+.1%})")
                        st.write(f"和局: **{dp:.1%}** (Edge: {de:+.1%})")
                    with c2:
                        st.write("**⚽ 進球模式與大小分**")
                        st.write(f"大分 2.5 潛力: **{ov:.1%}**")
                        st.write(f"聯賽風格: {bias['style']}")
                        st.info(f"💡 該場已根據「{bias['label']}」自動修正參數。")
                st.divider()
            except: continue

    with tab_tactics:
        st.subheader("⚙️ 聯賽診斷庫 (自動修正清單)")
        st.table(pd.DataFrame([{"聯賽": k, "標籤": v['label'], "分析": v['style']} for k, v in LEAGUE_BIAS.items()]))

if __name__ == "__main__":
    main()
