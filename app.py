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
# 🧠 2. 聯賽加權設定
# ==========================================
LEAGUE_BIAS = {
    "Premier League": {"adj": 1.05, "label": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 英超"},
    "La Liga": {"adj": 0.95, "label": "🇪🇸 西甲"},
    "Serie A": {"adj": 0.92, "label": "🇮🇹 意甲"},
    "Bundesliga": {"adj": 1.15, "label": "🇩🇪 德甲"},
    "Ligue 1": {"adj": 0.98, "label": "🇫🇷 法甲"},
    "Premier League - Russia": {"adj": 0.82, "label": "❄️ 俄超"}
}

# ==========================================
# 🎨 3. UI 視覺 (修正渲染邏輯)
# ==========================================
st.set_page_config(page_title="ZEUS PRO v61.0", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0d1117; color: #e6edf3; }
    .master-card {
        background: #161b22; border: 1px solid #30363d; border-radius: 12px;
        padding: 20px; margin-bottom: 20px; border-left: 6px solid #00ff88;
    }
    .status-bar { font-size: 0.85rem; color: #8b949e; margin-bottom: 15px; }
    .team-line { font-size: 1.3rem; font-weight: 800; margin: 12px 0; color: #ffffff; }
    .score-badge { background: #21262d; color: #58a6ff; padding: 4px 10px; border-radius: 5px; font-size: 0.85rem; border: 1px solid #30363d; margin-right: 8px; display: inline-block; font-family: monospace; }
    .rec-badge { background: #f1c40f; color: #000; padding: 6px 14px; border-radius: 8px; font-weight: 900; margin-right: 10px; display: inline-block; }
    .edge-val { color: #00ff88; font-weight: 700; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# ⚙️ 4. 演算引擎
# ==========================================
def run_simulation(h_o, d_o, a_o, league_name, n_sims=100000):
    bias = LEAGUE_BIAS.get(league_name, {"adj": 1.0, "label": "⚽ 常規"})
    margin = (1/h_o) + (1/d_o) + (1/a_o)
    ph, pd, pa = (1/h_o)/margin, (1/d_o)/margin, (1/a_o)/margin
    
    total_goals = 2.65 * bias['adj']
    h_l = total_goals * (ph / (ph + pa)) * 1.05
    a_l = total_goals * (pa / (ph + pa)) * 0.95
    
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
    scores = pd.Series(results).value_counts(normalize=True).head(3)
    
    return he, de, ae, recs, bias, scores

# ==========================================
# 🖥️ 5. 主程式
# ==========================================
def main():
    st.markdown("<h1 style='text-align:center; color:#00ff88;'>🛡️ ZEUS PREDICT PRO v61.0</h1>", unsafe_allow_html=True)
    
    # 建立頁籤
    tab1, tab2, tab3 = st.tabs(["🎯 實戰預測中心", "📚 歷史數據覆盤", "⚙️ 系統診斷"])

    with tab1:
        st.markdown(f"<div class='status-bar'>🚀 最後檢查：{datetime.now().strftime('%H:%M:%S')}</div>", unsafe_allow_html=True)
        
        # 1. API 抓取與除錯
        try:
            API_URL = f"https://api.the-odds-api.com/v4/sports/soccer/odds/?apiKey={st.secrets['ODDS_API_KEY']}&regions=eu&markets=h2h"
            resp = requests.get(API_URL)
            data = resp.json()
            
            if resp.status_code != 200:
                st.error(f"❌ API 報錯：{data.get('message', '未知錯誤')}")
                return
        except Exception as e:
            st.error(f"❌ 無法連接 API：{str(e)}")
            return

        if not data:
            st.warning("⚠️ 目前 API 沒有回傳任何賽事，請確認 API Key 餘額或稍後再試。")
        else:
            match_count = 0
            for m in data[:20]:
                try:
                    # 賠率擷取測試
                    bookmaker = m.get('bookmakers')
                    if not bookmaker: continue
                    
                    market = bookmaker[0]['markets'][0]['outcomes']
                    h_o = next(o['price'] for o in market if o['name'] == m['home_team'])
                    d_o = next(o['price'] for o in market if o['name'] == 'Draw')
                    a_o = next(o['price'] for o in market if o['name'] == m['away_team'])
                    
                    # 計算
                    he, de, ae, recs, bias, scores = run_simulation(h_o, d_o, a_o, m['sport_title'])

                    # 時間處理
                    start_time = datetime.strptime(m['commence_time'], "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=8)
                    time_str = start_time.strftime("%m/%d %H:%M")

                    # 資料庫寫入 (不影響 UI)
                    try:
                        conn = sqlite3.connect('zeus_data.db')
                        c = conn.cursor()
                        m_id = f"{m['id']}_{start_time.strftime('%m%d')}"
                        pred_str = " ".join(recs) if recs else "模型觀察中"
                        c.execute("INSERT OR IGNORE INTO matches (match_id, league, home, away, prediction, status, timestamp, start_time) VALUES (?,?,?,?,?,?,?,?)",
                                  (m_id, m['sport_title'], m['home_team'], m['away_team'], pred_str, "待定", datetime.now().strftime('%Y-%m-%d %H:%M'), time_str))
                        conn.commit()
                        conn.close()
                    except: pass

                    # 卡片渲染
                    score_tags = "".join([f"<div class='score-badge'>{s} ({p:.1%})</div>" for s, p in scores.items()])
                    rec_tags = "".join([f"<div class='rec-badge'>{r}</div>" for r in recs]) if recs else "<span style='color:#666;'>數據觀望中</span>"

                    st.markdown(f"""<div class="master-card">
<div style="display:flex; justify-content:space-between; font-size:0.8rem; color:#8b949e;">
<span>🏆 {m['sport_title']} | {bias['label']}</span>
<span>🕒 {time_str}</span>
</div>
<div class="team-line">{m['home_team']} <span style="color:#444;">vs</span> {m['away_team']}</div>
<div style="margin: 10px 0;">{score_tags}</div>
<div style="display:flex; justify-content:space-between; align-items:center; border-top:1px solid #30363d; padding-top:12px;">
<div>{rec_tags}</div>
<div class="edge-val">Edge: {max(he, de, ae):+.1%}</div>
</div>
</div>""", unsafe_allow_html=True)
                    match_count += 1
                except Exception as e:
                    # 這裡如果出錯會顯示在頁面上幫助我們抓 Bug
                    st.write(f"⚠️ 賽事解析錯誤 ({m.get('home_team', '未知')}): {str(e)}")
                    continue
            
            if match_count == 0:
                st.info("💡 API 有回傳數據，但暫無符合條件的比賽（可能賠率格式不符）。")

    with tab2:
        # 歷史覆盤保留
        st.markdown("### 📝 賽果覆盤編輯器")
        conn = sqlite3.connect('zeus_data.db')
        df = pd.read_sql_query("SELECT match_id, start_time, league, home, away, prediction, result, status FROM matches ORDER BY timestamp DESC LIMIT 50", conn)
        if not df.empty:
            edited_df = st.data_editor(df, use_container_width=True, hide_index=True)
            if st.button("💾 儲存更改"):
                c = conn.cursor()
                for _, r in edited_df.iterrows():
                    c.execute("UPDATE matches SET result=?, status=? WHERE match_id=?", (r['result'], r['status'], r['match_id']))
                conn.commit(); st.success("更新成功")
        conn.close()

    with tab3:
        st.markdown("### ⚙️ 系統診斷")
        if st.button("🗑️ 清空資料庫"):
            conn = sqlite3.connect('zeus_data.db'); c = conn.cursor()
            c.execute("DELETE FROM matches"); conn.commit(); conn.close()
            st.rerun()

if __name__ == "__main__":
    main()
