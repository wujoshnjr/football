import streamlit as st
import requests
import numpy as np
import pandas as pd
import sqlite3
from datetime import datetime, timedelta

# ==========================================
# 🔑 1. 初始化資料庫
# ==========================================
def init_db():
    conn = sqlite3.connect('zeus_data.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS matches 
                 (match_id TEXT PRIMARY KEY, league TEXT, home TEXT, away TEXT, 
                  prediction TEXT, result TEXT, status TEXT, 
                  timestamp TEXT, start_time TEXT)''')
    conn.commit()
    conn.close()

init_db()

# ==========================================
# 🧠 2. 聯賽配置
# ==========================================
LEAGUE_BIAS = {
    "Premier League": {"adj": 1.05, "label": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 英超"},
    "La Liga": {"adj": 0.95, "label": "🇪🇸 西甲"},
    "Serie A": {"adj": 0.92, "label": "🇮🇹 意甲"},
    "Bundesliga": {"adj": 1.15, "label": "🇩🇪 德甲"},
    "Ligue 1": {"adj": 0.98, "label": "🇫🇷 法甲"},
    "Premier League - Russia": {"adj": 0.82, "label": "❄️ 俄超"},
    "Allsvenskan - Sweden": {"adj": 1.10, "label": "🇸🇪 瑞典超"}
}

# ==========================================
# 🎨 3. UI 視覺 (修正渲染)
# ==========================================
st.set_page_config(page_title="ZEUS PRO v63.0", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0d1117; color: #e6edf3; }
    .master-card {
        background: #161b22; border: 1px solid #30363d; border-radius: 12px;
        padding: 20px; margin-bottom: 20px; border-left: 6px solid #00ff88;
    }
    .status-bar { font-size: 0.85rem; color: #8b949e; margin-bottom: 15px; }
    .team-line { font-size: 1.3rem; font-weight: 800; margin: 12px 0; color: #ffffff; }
    .score-badge { background: #21262d; color: #58a6ff; padding: 4px 10px; border-radius: 5px; font-size: 0.85rem; border: 1px solid #30363d; margin-right: 8px; display: inline-block; }
    .rec-badge { background: #f1c40f; color: #000; padding: 6px 14px; border-radius: 8px; font-weight: 900; margin-right: 10px; display: inline-block; }
    .edge-val { color: #00ff88; font-weight: 700; }
    .quota-info { color: #ffa500; font-size: 0.8rem; font-family: monospace; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# ⚙️ 4. 演算引擎 (修正變數衝突)
# ==========================================
def run_simulation(h_o, d_o, a_o, league_name, n_sims=100000):
    bias = LEAGUE_BIAS.get(league_name, {"adj": 1.0, "label": "⚽ 常規"})
    margin = (1/h_o) + (1/d_o) + (1/a_o)
    p_h, p_d, p_a = (1/h_o)/margin, (1/d_o)/margin, (1/a_o)/margin
    
    total_goals = 2.65 * bias['adj']
    h_l = total_goals * (p_h / (p_h + p_a)) * 1.05
    a_l = total_goals * (p_a / (p_h + p_a)) * 0.95
    
    h_s = np.random.poisson(h_l, n_sims)
    a_s = np.random.poisson(a_l, n_sims)
    
    sim_h, sim_d, sim_a = np.sum(h_s > a_s)/n_sims, np.sum(h_s == a_s)/n_sims, np.sum(h_s < a_s)/n_sims
    sim_ov25 = np.sum((h_s + a_s) > 2.5)/n_sims
    
    he, de, ae = sim_h-(1/h_o), sim_d-(1/d_o), sim_a-(1/a_o)
    
    recs = []
    if he > 0.035: recs.append("🏠 主勝")
    if ae > 0.035: recs.append("🚀 客勝")
    if de > 0.035: recs.append("🤝 和局")
    if sim_ov25 > 0.60: recs.append("🔥 大 2.5")
    elif sim_ov25 < 0.40: recs.append("🛡️ 小 2.5")
    
    results = [f"{h}:{a}" for h, a in zip(h_s[:5000], a_s[:5000])]
    top_scores = pd.Series(results).value_counts(normalize=True).head(3)
    
    return he, de, ae, recs, bias, top_scores

# ==========================================
# 🖥️ 5. 主流程
# ==========================================
def main():
    st.markdown("<h1 style='text-align:center; color:#00ff88;'>🛡️ ZEUS PREDICT PRO v63.0</h1>", unsafe_allow_html=True)
    
    tab1, tab2, tab3 = st.tabs(["🎯 實戰預測中心", "📚 歷史數據覆盤", "⚙️ 系統診斷"])

    # 全局變數用於診斷
    quota_remaining = "未知"
    api_error = None

    with tab1:
        try:
            API_KEY = st.secrets["ODDS_API_KEY"]
            API_URL = f"https://api.the-odds-api.com/v4/sports/soccer/odds/?apiKey={API_KEY}&regions=eu&markets=h2h"
            response = requests.get(API_URL)
            
            # 抓取額度信息 (The Odds API 會在 Header 回傳)
            quota_remaining = response.headers.get('x-requests-remaining', 'N/A')
            
            if response.status_code != 200:
                api_error = f"API 錯誤代碼: {response.status_code} | 信息: {response.text}"
                st.error(f"❌ 數據抓取失敗：{api_error}")
            else:
                data = response.json()
                st.markdown(f"<div class='status-bar'>🚀 最後同步：{datetime.now().strftime('%H:%M:%S')} | <span class='quota-info'>API 剩餘次數：{quota_remaining}</span></div>", unsafe_allow_html=True)
                
                if not data:
                    st.warning("⚠️ 目前暫無即時賽事數據。")
                else:
                    for m in data[:20]:
                        try:
                            bm = m.get('bookmakers')
                            if not bm: continue
                            outcomes = bm[0]['markets'][0]['outcomes']
                            h_o = next(o['price'] for o in outcomes if o['name'] == m['home_team'])
                            d_o = next(o['price'] for o in outcomes if o['name'] == 'Draw')
                            a_o = next(o['price'] for o in outcomes if o['name'] == m['away_team'])
                            
                            he, de, ae, recs, bias, scores = run_simulation(h_o, d_o, a_o, m['sport_title'])
                            start_dt = datetime.strptime(m['commence_time'], "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=8)
                            time_label = start_dt.strftime("%m/%d %H:%M")

                            # 自動存入資料庫
                            conn = sqlite3.connect('zeus_data.db')
                            c = conn.cursor()
                            m_id = f"{m['id']}_{start_dt.strftime('%m%d')}"
                            c.execute("INSERT OR IGNORE INTO matches (match_id, league, home, away, prediction, status, timestamp, start_time) VALUES (?,?,?,?,?,?,?,?)",
                                      (m_id, m['sport_title'], m['home_team'], m['away_team'], " ".join(recs), "待定", datetime.now().strftime('%Y-%m-%d %H:%M'), time_label))
                            conn.commit(); conn.close()

                            # 渲染卡片
                            score_html = "".join([f"<div class='score-badge'>{s} ({p:.1%})</div>" for s, p in scores.items()])
                            rec_html = "".join([f"<div class='rec-badge'>{r}</div>" for r in recs]) if recs else "模型觀察中"
                            
                            st.markdown(f"""<div class="master-card">
                            <div style="display:flex; justify-content:space-between; font-size:0.8rem; color:#8b949e;">
                            <span>🏆 {m['sport_title']} | {bias['label']}</span>
                            <span>🕒 {time_label}</span>
                            </div>
                            <div class="team-line">{m['home_team']} <span style="color:#444;">vs</span> {m['away_team']}</div>
                            <div style="margin: 10px 0;">{score_html}</div>
                            <div style="display:flex; justify-content:space-between; align-items:center; border-top:1px solid #30363d; padding-top:12px;">
                            <div>{rec_html}</div>
                            <div class="edge-val">Edge: {max(he, de, ae):+.1%}</div>
                            </div>
                            </div>""", unsafe_allow_html=True)
                        except: continue
        except Exception as e:
            st.error(f"⚠️ 系統運行異常: {str(e)}")

    with tab2:
        st.markdown("### 📝 賽果紀錄編輯器")
        conn = sqlite3.connect('zeus_data.db')
        df = pd.read_sql_query("SELECT match_id, start_time, league, home, away, prediction, result, status FROM matches ORDER BY timestamp DESC LIMIT 60", conn)
        if not df.empty:
            edited = st.data_editor(df, use_container_width=True, hide_index=True)
            if st.button("💾 儲存修改內容"):
                c = conn.cursor()
                for _, r in edited.iterrows():
                    c.execute("UPDATE matches SET result=?, status=? WHERE match_id=?", (r['result'], r['status'], r['match_id']))
                conn.commit(); st.success("紀錄已更新")
        conn.close()

    with tab3:
        st.markdown("### ⚙️ 系統與 API 狀態")
        st.write(f"📊 **API 剩餘額度**：{quota_remaining} (每月 500 次)")
        if api_error:
            st.error(f"🚨 最近一次 API 報錯：{api_error}")
        
        if st.button("🗑️ 強制清空歷史數據"):
            conn = sqlite3.connect('zeus_data.db'); c = conn.cursor()
            c.execute("DELETE FROM matches"); conn.commit(); conn.close()
            st.rerun()

if __name__ == "__main__":
    main()
