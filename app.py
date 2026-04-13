import streamlit as st
import requests
import numpy as np
import pandas as pd
import sqlite3
from datetime import datetime, timedelta

# ==========================================
# 🔑 1. 初始化資料庫 (永久儲存歷史紀錄)
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
# ⚡ 2. 數據抓取引擎 (含 10 分鐘緩存機制)
# ==========================================
@st.cache_data(ttl=600) # 每10分鐘才會真正去抓一次 API，節省額度
def fetch_odds_data(api_key):
    url = f"https://api.the-odds-api.com/v4/sports/soccer/odds/?apiKey={api_key}&regions=eu&markets=h2h"
    try:
        response = requests.get(url)
        return response.status_code, response.json(), response.headers
    except Exception as e:
        return 500, str(e), {}

# ==========================================
# 🧠 3. 核心模擬演算 (Poisson Distribution)
# ==========================================
LEAGUE_BIAS = {
    "Premier League": {"adj": 1.05, "label": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 英超"},
    "La Liga": {"adj": 0.95, "label": "🇪🇸 西甲"},
    "Serie A": {"adj": 0.92, "label": "🇮🇹 意甲"},
    "Bundesliga": {"adj": 1.15, "label": "🇩🇪 德甲"},
    "Ligue 1": {"adj": 0.98, "label": "🇫🇷 法甲"},
    "Premier League - Russia": {"adj": 0.82, "label": "❄️ 俄超 (防守強)"},
    "Allsvenskan - Sweden": {"adj": 1.10, "label": "🇸🇪 瑞典超"},
    "Turkey Super League": {"adj": 1.05, "label": "🇹🇷 土超"}
}

def run_simulation(h_o, d_o, a_o, league_name, n_sims=100000):
    bias = LEAGUE_BIAS.get(league_name, {"adj": 1.0, "label": "⚽ 常規"})
    margin = (1/h_o) + (1/d_o) + (1/a_o)
    
    # 這裡使用 p_home 等變數，避免與 pandas 的 pd 衝突
    p_home = (1/h_o)/margin
    p_draw = (1/d_o)/margin
    p_away = (1/a_o)/margin
    
    total_goals = 2.65 * bias['adj']
    h_lambda = total_goals * (p_home / (p_home + p_away)) * 1.05
    a_lambda = total_goals * (p_away / (p_home + p_away)) * 0.95
    
    h_s = np.random.poisson(h_lambda, n_sims)
    a_s = np.random.poisson(a_lambda, n_sims)
    
    sim_h = np.sum(h_s > a_s)/n_sims
    sim_d = np.sum(h_s == a_s)/n_sims
    sim_a = np.sum(h_s < a_s)/n_sims
    sim_ov25 = np.sum((h_s + a_s) > 2.5)/n_sims
    
    he, de, ae = sim_h-(1/h_o), sim_d-(1/d_o), sim_a-(1/a_o)
    
    recs = []
    if he > 0.04: recs.append("🏠 主勝")
    if ae > 0.04: recs.append("🚀 客勝")
    if de > 0.04: recs.append("🤝 和局")
    if sim_ov25 > 0.62: recs.append("🔥 大 2.5")
    elif sim_ov25 < 0.38: recs.append("🛡️ 小 2.5")
    
    results = [f"{h}:{a}" for h, a in zip(h_s[:5000], a_s[:5000])]
    scores = pd.Series(results).value_counts(normalize=True).head(3)
    
    return he, de, ae, recs, bias, scores

# ==========================================
# 🎨 4. CSS 視覺美化 (深色專業風)
# ==========================================
def apply_styles():
    st.markdown("""
    <style>
        .stApp { background-color: #0d1117; color: #e6edf3; }
        .master-card {
            background: #161b22; border: 1px solid #30363d; border-radius: 12px;
            padding: 20px; margin-bottom: 20px; border-left: 6px solid #00ff88;
        }
        .team-line { font-size: 1.3rem; font-weight: 800; margin: 12px 0; color: #ffffff; }
        .score-badge { background: #21262d; color: #58a6ff; padding: 4px 10px; border-radius: 5px; font-size: 0.85rem; border: 1px solid #30363d; margin-right: 8px; display: inline-block; font-family: monospace; }
        .rec-badge { background: #f1c40f; color: #000; padding: 6px 14px; border-radius: 8px; font-weight: 900; margin-right: 10px; display: inline-block; }
        .edge-val { color: #00ff88; font-weight: 700; }
        .quota-bar { font-size: 0.8rem; color: #ffa500; font-family: monospace; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 🖥️ 5. 主程式邏輯
# ==========================================
def main():
    apply_styles()
    st.markdown("<h1 style='text-align:center; color:#00ff88;'>🛡️ ZEUS PREDICT PRO v65.0</h1>", unsafe_allow_html=True)
    
    tab1, tab2, tab3 = st.tabs(["🎯 實戰預測", "📚 歷史覆盤", "⚙️ 系統診斷"])

    # 讀取 Secrets
    try:
        api_key = st.secrets["ODDS_API_KEY"]
    except:
        st.error("❌ 未偵測到 API Key，請檢查 Streamlit Secrets 設定。")
        return

    with tab1:
        status_code, data, headers = fetch_odds_data(api_key)
        remaining = headers.get('x-requests-remaining', 'N/A')
        
        if status_code == 401 or status_code == 429:
            st.error(f"🚨 API 無法使用：{data.get('message', '額度已耗盡')}")
            return
        elif status_code != 200:
            st.error(f"❌ API 連線錯誤：{status_code}")
            return

        st.markdown(f"<p class='quota-bar'>最後更新：{datetime.now().strftime('%H:%M:%S')} | 💎 API 剩餘額度：{remaining}</p>", unsafe_allow_html=True)

        if not data:
            st.warning("⚠️ 目前暫無即時賽事。")
        else:
            for m in data[:25]:
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
                    pred_txt = " ".join(recs) if recs else "數據觀望中"
                    c.execute("INSERT OR IGNORE INTO matches (match_id, league, home, away, prediction, status, timestamp, start_time) VALUES (?,?,?,?,?,?,?,?)",
                              (m_id, m['sport_title'], m['home_team'], m['away_team'], pred_txt, "待定", datetime.now().strftime('%Y-%m-%d %H:%M'), time_label))
                    conn.commit(); conn.close()

                    # 渲染 UI 卡片
                    score_html = "".join([f"<div class='score-badge'>{s} ({p:.1%})</div>" for s, p in scores.items()])
                    rec_html = "".join([f"<div class='rec-badge'>{r}</div>" for r in recs]) if recs else "模型分析中"
                    
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

    with tab2:
        st.markdown("### 📝 賽果覆盤編輯器")
        conn = sqlite3.connect('zeus_data.db')
        df = pd.read_sql_query("SELECT match_id, start_time, league, home, away, prediction, result, status FROM matches ORDER BY timestamp DESC LIMIT 100", conn)
        if not df.empty:
            edited = st.data_editor(df, column_config={
                "match_id": None,
                "status": st.column_config.SelectboxColumn("狀態", options=["待定", "✅ 命中", "❌ 未中", "➖ 走水"])
            }, use_container_width=True, hide_index=True)
            if st.button("💾 儲存修改內容", use_container_width=True):
                c = conn.cursor()
                for _, r in edited.iterrows():
                    c.execute("UPDATE matches SET result=?, status=? WHERE match_id=?", (r['result'], r['status'], r['match_id']))
                conn.commit(); st.success("紀錄已成功更新！")
        else: st.info("目前尚無紀錄數據。")
        conn.close()

    with tab3:
        st.markdown("### ⚙️ 系統診斷")
        st.write(f"📊 **API 剩餘額度**：{remaining}")
        if st.button("🗑️ 清空所有歷史數據"):
            conn = sqlite3.connect('zeus_data.db'); c = conn.cursor()
            c.execute("DELETE FROM matches"); conn.commit(); conn.close()
            st.rerun()

if __name__ == "__main__":
    main()
