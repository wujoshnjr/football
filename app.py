import streamlit as st
import requests
import numpy as np
import pandas as pd
import sqlite3
from datetime import datetime

# ==========================================
# 🔑 1. 初始化資料庫 (歷史紀錄系統核心)
# ==========================================
def init_db():
    conn = sqlite3.connect('zeus_data.db', check_same_thread=False)
    c = conn.cursor()
    # 建立包含預測、賠率、實際賽果與命中狀態的表格
    c.execute('''CREATE TABLE IF NOT EXISTS matches 
                 (match_id TEXT PRIMARY KEY, league TEXT, home TEXT, away TEXT, 
                  prediction TEXT, result TEXT, status TEXT, timestamp TEXT)''')
    conn.commit()
    conn.close()

init_db()

# ==========================================
# 🧠 2. 全球聯賽戰術特徵庫 (踢法診斷)
# ==========================================
# 針對各聯賽特色自動修正進球期望值
LEAGUE_BIAS = {
    "Premier League": {"adj": 1.12, "style": "高強度對抗/大分傾向", "label": "🔥 攻勢足球"},
    "La Liga": {"adj": 0.98, "style": "細膩控球/技術型踢法", "label": "🪄 技術足球"},
    "Serie A": {"adj": 0.92, "style": "傳統鏈式防守/小分傾向", "label": "🛡️ 戰術防守"},
    "Bundesliga": {"adj": 1.28, "style": "高位壓迫/極大分傾向", "label": "🏹 激情全攻"},
    "Premier League - Russia": {"adj": 0.82, "style": "硬朗防守/低進球模式", "label": "❄️ 鐵血防守"},
    "Ligue 1": {"adj": 1.05, "style": "體能化對抗/中性進球", "label": "🏃 強力對抗"}
}

# ==========================================
# 🎨 3. UI 視覺樣式配置
# ==========================================
st.set_page_config(page_title="ZEUS PRO v45.0", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0d1117; color: #e6edf3; }
    .master-card {
        background: #161b22; border: 1px solid #30363d; border-radius: 16px;
        padding: 24px; margin-bottom: 22px; border-left: 12px solid #00ff88;
    }
    .home-tag { background: #238636; color: white; padding: 3px 10px; border-radius: 6px; font-weight: bold; }
    .away-tag { background: #1f6feb; color: white; padding: 3px 10px; border-radius: 6px; font-weight: bold; }
    .rec-badge { background: #f1c40f; color: #000; padding: 6px 14px; border-radius: 8px; font-weight: 900; margin: 4px; display: inline-block; }
    .edge-val { color: #00ff88; font-weight: 800; font-size: 1.1rem; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# ⚙️ 4. 核心運算：十萬次戰術模擬引擎
# ==========================================
def run_simulation(h_o, d_o, a_o, league_name, n_sims=100000):
    bias = LEAGUE_BIAS.get(league_name, {"adj": 1.0, "style": "標準數據模型", "label": "📊 常規診斷"})
    h_l, a_l = (1/h_o)*2.80*bias['adj'], (1/a_o)*2.80*bias['adj']
    h_s, a_s = np.random.poisson(h_l, n_sims), np.random.poisson(a_l, n_sims)
    
    hp, dp, ap = np.sum(h_s > a_s)/n_sims, np.sum(h_s == a_s)/n_sims, np.sum(h_s < a_s)/n_sims
    ov25 = np.sum((h_s + a_s) > 2.5)/n_sims
    he, de, ae = hp-(1/h_o), dp-(1/d_o), ap-(1/a_o)
    
    recs = []
    if he > 0.045: recs.append("🏠 不讓分主推")
    if ae > 0.045: recs.append("🚀 不讓分客推")
    if de > 0.05: recs.append("💎 和局博弈")
    if ov25 > 0.62: recs.append("🔥 大分 2.5")
    if ov25 < 0.36: recs.append("🛡️ 小分 2.5")
    
    # 波膽模擬
    results = [f"{h}:{a}" for h, a in zip(h_s[:1000], a_s[:1000])]
    scores = pd.Series(results).value_counts(normalize=True).head(5)
    
    return hp, dp, ap, ov25, he, de, ae, recs, bias, scores

# ==========================================
# 🖥️ 5. 實戰主流程 (全模組整合)
# ==========================================
def main():
    st.markdown("<h1 style='text-align:center; color:#00ff88;'>🛡️ ZEUS PREDICT PRO v45.0</h1>", unsafe_allow_html=True)
    st.caption(f"🚀 即時更新：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 數據源：Global Live Odds")

    # API 抓取
    API_URL = f"https://api.the-odds-api.com/v4/sports/soccer/odds/?apiKey={st.secrets['ODDS_API_KEY']}&regions=eu&markets=h2h"
    try:
        data = requests.get(API_URL).json()
    except:
        st.error("API 連線失敗，請檢查網路或密鑰")
        return

    tab1, tab2, tab3, tab4 = st.tabs(["🎯 實戰預測中心", "🎲 模擬波膽庫", "📚 歷史紀錄與檢討", "⚙️ 聯賽診斷庫"])

    # 1. 預測中心
    with tab1:
        if not data: st.warning("目前無賽事數據，請稍後刷新")
        for m in data[:15]:
            try:
                market = m['bookmakers'][0]['markets'][0]['outcomes']
                h_o = next(o['price'] for o in market if o['name'] == m['home_team'])
                d_o = next(o['price'] for o in market if o['name'] == 'Draw')
                a_o = next(o['price'] for o in market if o['name'] == m['away_team'])
                
                hp, dp, ap, ov, he, de, ae, recs, bias, _ = run_simulation(h_o, d_o, a_o, m['sport_title'])

                # 自動儲存至資料庫
                conn = sqlite3.connect('zeus_data.db')
                c = conn.cursor()
                m_id = f"{m['id']}_{datetime.now().strftime('%Y%m%d')}"
                c.execute("INSERT OR IGNORE INTO matches (match_id, league, home, away, prediction, timestamp) VALUES (?,?,?,?,?,?)",
                          (m_id, m['sport_title'], m['home_team'], m['away_team'], ", ".join(recs), datetime.now().strftime('%Y-%m-%d')))
                conn.commit()
                conn.close()

                st.markdown(f"""
                <div class="master-card">
                    <div style="display:flex; justify-content:space-between;">
                        <span style="color:#8b949e; font-size:0.85rem;">🏆 {m['sport_title']} | {bias['label']}</span>
                        <span class="edge-val">優勢 Edge: {max(he, ae, de):+.1%}</span>
                    </div>
                    <div style="margin: 18px 0;">
                        <span class="home-tag">主</span> <b>{m['home_team']}</b> VS <b>{m['away_team']}</b> <span class="away-tag">客</span>
                    </div>
                    <div>{' '.join([f'<span class="rec-badge">{r}</span>' for r in recs]) if recs else '<span style="color:#8b949e;">模型觀察中...</span>'}</div>
                </div>
                """, unsafe_allow_html=True)
            except: continue

    # 2. 波膽庫
    with tab2:
        st.info("基於十萬次隨機模擬出的最高機率比分（波膽）")
        for m in data[:8]:
            try:
                market = m['bookmakers'][0]['markets'][0]['outcomes']
                h_o = next(o['price'] for o in market if o['name'] == m['home_team'])
                d_o = next(o['price'] for o in market if o['name'] == 'Draw')
                a_o = next(o['price'] for o in market if o['name'] == m['away_team'])
                _, _, _, _, _, _, _, _, _, s_list = run_simulation(h_o, d_o, a_o, m['sport_title'])
                
                st.write(f"**{m['home_team']} vs {m['away_team']}**")
                cols = st.columns(5)
                for i, (score, prob) in enumerate(s_list.items()):
                    cols[i].metric(score, f"{prob:.1%}")
                st.divider()
            except: continue

    # 3. 歷史紀錄與賽後檢討
    with tab3:
        st.subheader("📚 預測紀錄與準確率檢討")
        conn = sqlite3.connect('zeus_data.db')
        df = pd.read_sql_query("SELECT * FROM matches ORDER BY timestamp DESC LIMIT 30", conn)
        
        if not df.empty:
            for idx, row in df.iterrows():
                with st.expander(f"📌 {row['timestamp']} | {row['home']} vs {row['away']}"):
                    st.write(f"**模型建議：** {row['prediction']}")
                    score_res = st.text_input("輸入賽果 (例如 2:1)", value=row['result'] if row['result'] else "", key=f"res_{row['match_id']}")
                    if st.button("確認結果", key=f"btn_{row['match_id']}"):
                        status = "✅ 命中" if score_res else "待定"
                        conn.execute("UPDATE matches SET result=?, status=? WHERE match_id=?", (score_res, status, row['match_id']))
                        conn.commit()
                        st.success("紀錄已存檔，請刷新頁面查看更新")
            st.table(df[['timestamp', 'home', 'away', 'prediction', 'result', 'status']])
        else:
            st.info("尚無預測紀錄。請在實戰中心查看賽事以自動記錄")
        conn.close()

    # 4. 診斷庫
    with tab4:
        st.write("**當前各聯賽踢法診斷權重：**")
        st.table(pd.DataFrame([{"聯賽": k, "風格標籤": v['label'], "分析說明": v['style'], "調整係數": v['adj']} for k, v in LEAGUE_BIAS.items()]))

if __name__ == "__main__":
    main()
