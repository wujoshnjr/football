import streamlit as st
import requests
import numpy as np
import pandas as pd
import sqlite3
from datetime import datetime, timedelta

# ==========================================
# 🔑 1. 初始化資料庫 (新增開賽時間欄位)
# ==========================================
def init_db():
    conn = sqlite3.connect('zeus_data.db', check_same_thread=False)
    c = conn.cursor()
    # 增加 start_time 欄位以記錄比賽具體時間
    c.execute('''CREATE TABLE IF NOT EXISTS matches 
                 (match_id TEXT PRIMARY KEY, league TEXT, home TEXT, away TEXT, 
                  prediction TEXT, result TEXT, status TEXT, 
                  timestamp TEXT, start_time TEXT)''')
    conn.commit()
    conn.close()

init_db()

# ==========================================
# 🧠 2. 全球聯賽戰術特徵庫
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
# 🎨 3. UI 視覺樣式配置
# ==========================================
st.set_page_config(page_title="ZEUS PRO v46.0", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0d1117; color: #e6edf3; }
    .master-card {
        background: #161b22; border: 1px solid #30363d; border-radius: 16px;
        padding: 24px; margin-bottom: 22px; border-left: 12px solid #00ff88;
    }
    .time-tag { color: #8b949e; font-size: 0.85rem; font-weight: bold; }
    .home-tag { background: #238636; color: white; padding: 3px 10px; border-radius: 6px; font-weight: bold; }
    .away-tag { background: #1f6feb; color: white; padding: 3px 10px; border-radius: 6px; font-weight: bold; }
    .rec-badge { background: #f1c40f; color: #000; padding: 6px 14px; border-radius: 8px; font-weight: 900; margin: 4px; display: inline-block; }
    .edge-val { color: #00ff88; font-weight: 800; font-size: 1.1rem; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# ⚙️ 4. 核心運算引擎
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
    
    results = [f"{h}:{a}" for h, a in zip(h_s[:1000], a_s[:1000])]
    scores = pd.Series(results).value_counts(normalize=True).head(5)
    
    return hp, dp, ap, ov25, he, de, ae, recs, bias, scores

# ==========================================
# 🖥️ 5. 實戰主流程 (加入時間處理邏輯)
# ==========================================
def main():
    st.markdown("<h1 style='text-align:center; color:#00ff88;'>🛡️ ZEUS PREDICT PRO v46.0</h1>", unsafe_allow_html=True)
    
    API_URL = f"https://api.the-odds-api.com/v4/sports/soccer/odds/?apiKey={st.secrets['ODDS_API_KEY']}&regions=eu&markets=h2h"
    
    try:
        data = requests.get(API_URL).json()
    except:
        st.error("API 連線失敗")
        return

    tab1, tab2, tab3, tab4 = st.tabs(["🎯 實戰預測中心", "🎲 模擬波膽庫", "📚 歷史紀錄與檢討", "⚙️ 聯賽診斷庫"])

    with tab1:
        if not data: st.warning("目前無賽事數據")
        for m in data[:15]:
            try:
                # 處理開賽時間 (UTC 轉在地時間 +8)
                commence_time = datetime.strptime(m['commence_time'], "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=8)
                time_str = commence_time.strftime("%m/%d %H:%M")

                market = m['bookmakers'][0]['markets'][0]['outcomes']
                h_o = next(o['price'] for o in market if o['name'] == m['home_team'])
                d_o = next(o['price'] for o in market if o['name'] == 'Draw')
                a_o = next(o['price'] for o in market if o['name'] == m['away_team'])
                
                hp, dp, ap, ov, he, de, ae, recs, bias, _ = run_simulation(h_o, d_o, a_o, m['sport_title'])

                # 儲存至資料庫 (含開賽時間)
                conn = sqlite3.connect('zeus_data.db')
                c = conn.cursor()
                m_id = f"{m['id']}_{commence_time.strftime('%Y%m%d')}"
                c.execute("INSERT OR IGNORE INTO matches (match_id, league, home, away, prediction, timestamp, start_time) VALUES (?,?,?,?,?,?,?)",
                          (m_id, m['sport_title'], m['home_team'], m['away_team'], ", ".join(recs), datetime.now().strftime('%Y-%m-%d'), time_str))
                conn.commit()
                conn.close()

                st.markdown(f"""
                <div class="master-card">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <span style="color:#8b949e; font-size:0.85rem;">🏆 {m['sport_title']} | {bias['label']}</span>
                        <span class="time-tag">🕒 開賽：{time_str}</span>
                    </div>
                    <div style="margin: 15px 0;">
                        <span class="home-tag">主</span> <b>{m['home_team']}</b> VS <b>{m['away_team']}</b> <span class="away-tag">客</span>
                    </div>
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div>{' '.join([f'<span class="rec-badge">{r}</span>' for r in recs]) if recs else '觀察中'}</div>
                        <span class="edge-val">Edge: {max(he, ae, de):+.1%}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            except: continue

    with tab2:
        st.info("十萬次隨機模擬最高機率比分")
        for m in data[:8]:
            try:
                time_str = (datetime.strptime(m['commence_time'], "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=8)).strftime("%H:%M")
                market = m['bookmakers'][0]['markets'][0]['outcomes']
                h_o, d_o, a_o = [next(o['price'] for o in market if o['name'] == x) for x in [m['home_team'], 'Draw', m['away_team']]]
                _, _, _, _, _, _, _, _, _, s_list = run_simulation(h_o, d_o, a_o, m['sport_title'])
                
                st.write(f"**[{time_str}] {m['home_team']} vs {m['away_team']}**")
                cols = st.columns(5)
                for i, (score, prob) in enumerate(s_list.items()):
                    cols[i].metric(score, f"{prob:.1%}")
                st.divider()
            except: continue

    with tab3:
        st.subheader("📚 歷史紀錄與精準度回測")
        conn = sqlite3.connect('zeus_data.db')
        df = pd.read_sql_query("SELECT * FROM matches ORDER BY start_time DESC LIMIT 30", conn)
        
        if not df.empty:
            for idx, row in df.iterrows():
                with st.expander(f"🕒 {row['start_time']} | {row['home']} vs {row['away']}"):
                    st.write(f"**建議：** {row['prediction']}")
                    score_res = st.text_input("輸入賽果", value=row['result'] if row['result'] else "", key=f"res_{row['match_id']}")
                    if st.button("確認存檔", key=f"btn_{row['match_id']}"):
                        conn.execute("UPDATE matches SET result=?, status=? WHERE match_id=?", (score_res, "✅ 已結算" if score_res else "待定", row['match_id']))
                        conn.commit()
                        st.rerun()
            st.table(df[['start_time', 'home', 'away', 'prediction', 'result', 'status']])
        conn.close()

    with tab4:
        st.table(pd.DataFrame([{"聯賽": k, "風格": v['style'], "權重": v['adj']} for k, v in LEAGUE_BIAS.items()]))

if __name__ == "__main__":
    main()
