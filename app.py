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
    try:
        c.execute("SELECT start_time FROM matches LIMIT 1")
    except sqlite3.OperationalError:
        c.execute("ALTER TABLE matches ADD COLUMN start_time TEXT")
        conn.commit()
    conn.close()

init_db()

# ==========================================
# 🧠 2. 聯賽特性修正 (調高進球權重)
# ==========================================
LEAGUE_BIAS = {
    "Premier League": {"adj": 1.20, "label": "🔥 攻勢足球"},
    "La Liga": {"adj": 1.05, "label": "🪄 技術足球"},
    "Serie A": {"adj": 0.98, "label": "🛡️ 戰術防守"},
    "Bundesliga": {"adj": 1.35, "label": "🏹 激情全攻"},
    "Ligue 1": {"adj": 1.10, "label": "🏃 強力對抗"},
    "Allsvenskan - Sweden": {"adj": 1.15, "label": "🇸🇪 北歐大分"},
    "Turkey Super League": {"adj": 1.12, "label": "🇹🇷 土超狂熱"}
}

# ==========================================
# 🎨 3. UI 視覺配置
# ==========================================
st.set_page_config(page_title="ZEUS PRO v48.0", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0d1117; color: #e6edf3; }
    .master-card {
        background: #161b22; border: 1px solid #30363d; border-radius: 12px;
        padding: 20px; margin-bottom: 20px; border-left: 8px solid #00ff88;
    }
    .time-tag { color: #8b949e; font-size: 0.8rem; }
    .team-name { font-size: 1.15rem; font-weight: 700; margin: 10px 0; }
    .rec-badge { background: #f1c40f; color: #000; padding: 5px 12px; border-radius: 6px; font-weight: 800; margin-right: 5px; }
    .score-badge { background: #21262d; color: #58a6ff; padding: 4px 10px; border-radius: 5px; font-size: 0.9rem; border: 1px solid #30363d; margin-right: 8px; font-family: monospace; }
    .edge-val { color: #00ff88; font-weight: 800; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# ⚙️ 4. 核心演算引擎 (解放火力)
# ==========================================
def run_simulation(h_o, d_o, a_o, league_name, n_sims=100000):
    bias = LEAGUE_BIAS.get(league_name, {"adj": 1.05, "label": "📊 常規診斷"})
    
    # 賠率還原與水錢校正
    margin = (1/h_o) + (1/d_o) + (1/a_o)
    ph, pa = (1/h_o)/margin, (1/a_o)/margin
    
    # 【核心調整】：提升基準期望進球至 3.1 球，解決預測太保守的問題
    total_expected_goals = 3.10 * bias['adj']
    
    # 分攤進球權重 (給予強隊更高權重，產生高比分)
    h_l = total_expected_goals * (ph**0.85 / (ph**0.85 + pa**0.85)) * 1.08
    a_l = total_expected_goals * (pa**0.85 / (ph**0.85 + pa**0.85)) * 0.92
    
    h_s = np.random.poisson(h_l, n_sims)
    a_s = np.random.poisson(a_l, n_sims)
    
    hp, dp, ap = np.sum(h_s > a_s)/n_sims, np.sum(h_s == a_s)/n_sims, np.sum(h_s < a_s)/n_sims
    ov25 = np.sum((h_s + a_s) > 2.5)/n_sims
    he, de, ae = hp-(1/h_o), dp-(1/d_o), ap-(1/a_o)
    
    recs = []
    # 放寬門檻讓推薦更積極
    if he > 0.02: recs.append("🏠 主勝推")
    if ae > 0.02: recs.append("🚀 客勝推")
    if de > 0.03: recs.append("💎 和局博弈")
    if ov25 > 0.52: recs.append("🔥 大分 2.5")
    elif ov25 < 0.40: recs.append("🛡️ 小分 2.5")
    
    # 取樣模擬波膽
    results = [f"{h}:{a}" for h, a in zip(h_s[:2000], a_s[:2000])]
    scores = pd.Series(results).value_counts(normalize=True).head(3)
    
    return hp, dp, ap, ov25, he, de, ae, recs, bias, scores

# ==========================================
# 🖥️ 5. 實戰主流程
# ==========================================
def main():
    st.markdown("<h1 style='text-align:center; color:#00ff88;'>🛡️ ZEUS PREDICT PRO v48.0</h1>", unsafe_allow_html=True)
    
    try:
        API_URL = f"https://api.the-odds-api.com/v4/sports/soccer/odds/?apiKey={st.secrets['ODDS_API_KEY']}&regions=eu&markets=h2h"
        data = requests.get(API_URL).json()
    except:
        st.error("❌ 無法獲取 API 數據，請確認 Secret Key。")
        return

    tabs = st.tabs(["🎯 實戰分析中心", "📚 歷史數據回溯", "⚙️ 系統診斷"])

    with tabs[0]:
        if not data: st.warning("目前無賽事資訊")
        for m in data[:20]:
            try:
                # 時間處理
                start = datetime.strptime(m['commence_time'], "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=8)
                time_str = start.strftime("%m/%d %H:%M")
                
                market = m['bookmakers'][0]['markets'][0]['outcomes']
                h_o = next(o['price'] for o in market if o['name'] == m['home_team'])
                d_o = next(o['price'] for o in market if o['name'] == 'Draw')
                a_o = next(o['price'] for o in market if o['name'] == m['away_team'])
                
                _, _, _, _, he, de, ae, recs, bias, scores = run_simulation(h_o, d_o, a_o, m['sport_title'])

                # 構建波膽 HTML (修正導致渲染錯誤的嵌套引號)
                score_html = "".join([f"<span class='score-badge'>{s} ({p:.1%})</span>" for s, p in scores.items()])
                rec_html = "".join([f"<span class='rec-badge'>{r}</span>" for r in recs]) if recs else "<span style='color:#6e7681;'>模型觀察中...</span>"

                # 顯示主卡片
                st.markdown(f"""
                <div class="master-card">
                    <div style="display:flex; justify-content:space-between;">
                        <span style="color:#8b949e; font-size:0.85rem;">🏆 {m['sport_title']} | {bias['label']}</span>
                        <span class="time-tag">🕒 開賽：{time_str}</span>
                    </div>
                    <div class="team-name">
                        <span style="color:#238636;">[主]</span> {m['home_team']} 
                        <span style="color:#8b949e; font-size:0.9rem;"> VS </span> 
                        {m['away_team']} <span style="color:#1f6feb;">[客]</span>
                    </div>
                    <div style="margin: 15px 0;">
                        <span style="font-size:0.85rem; color:#8b949e;">🎲 模擬比分：</span>{score_html}
                    </div>
                    <div style="display:flex; justify-content:space-between; align-items:center; border-top:1px solid #30363d; padding-top:12px;">
                        <div>{rec_html}</div>
                        <div class="edge-val">優勢 Edge: {max(he, ae, de):+.1%}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            except: continue

    with tabs[1]:
        conn = sqlite3.connect('zeus_data.db')
        df = pd.read_sql_query("SELECT * FROM matches ORDER BY start_time DESC LIMIT 40", conn)
        if not df.empty:
            st.dataframe(df, use_container_width=True)
        else:
            st.info("尚無歷史數據紀錄")
        conn.close()

if __name__ == "__main__":
    main()

