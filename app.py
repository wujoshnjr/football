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
# 🧠 2. 聯賽特性 (Berserker Mode)
# ==========================================
LEAGUE_BIAS = {
    "Premier League": {"adj": 1.25, "label": "🔥 攻勢足球"},
    "La Liga": {"adj": 1.10, "label": "🪄 技術足球"},
    "Serie A": {"adj": 1.05, "label": "🛡️ 戰術防守"},
    "Bundesliga": {"adj": 1.45, "label": "🏹 激情全攻"},
    "Ligue 1": {"adj": 1.15, "label": "🏃 強力對抗"},
    "Allsvenskan - Sweden": {"adj": 1.25, "label": "🇸🇪 北歐大分"},
    "Turkey Super League": {"adj": 1.20, "label": "🇹🇷 土超狂熱"}
}

# ==========================================
# 🎨 3. UI 視覺配置
# ==========================================
st.set_page_config(page_title="ZEUS PRO v49.0", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0d1117; color: #e6edf3; }
    .master-card {
        background: #161b22; border: 1px solid #30363d; border-radius: 12px;
        padding: 20px; margin-bottom: 20px; border-left: 8px solid #00ff88;
    }
    .time-tag { color: #8b949e; font-size: 0.8rem; }
    .team-line { font-size: 1.2rem; font-weight: 700; margin: 12px 0; }
    .rec-badge { background: #f1c40f; color: #000; padding: 5px 12px; border-radius: 6px; font-weight: 800; margin-right: 8px; display: inline-block; }
    .score-badge { background: #21262d; color: #58a6ff; padding: 4px 10px; border-radius: 5px; font-size: 0.95rem; border: 1px solid #30363d; margin-right: 8px; font-family: monospace; display: inline-block; }
    .edge-val { color: #00ff88; font-weight: 800; font-size: 1.1rem; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# ⚙️ 4. 核心演算引擎 (火力全開)
# ==========================================
def run_simulation(h_o, d_o, a_o, league_name, n_sims=100000):
    bias = LEAGUE_BIAS.get(league_name, {"adj": 1.10, "label": "📊 常規診斷"})
    
    # 賠率還原
    margin = (1/h_o) + (1/d_o) + (1/a_o)
    ph, pa = (1/h_o)/margin, (1/a_o)/margin
    
    # 【核心解放】：將基準進球拉高到 3.5，並增加實力權重冪次
    total_goals = 3.50 * bias['adj']
    h_l = total_goals * (ph**1.2 / (ph**1.2 + pa**1.2)) * 1.05
    a_l = total_goals * (pa**1.2 / (ph**1.2 + pa**1.2)) * 0.95
    
    h_s = np.random.poisson(h_l, n_sims)
    a_s = np.random.poisson(a_l, n_sims)
    
    hp, dp, ap = np.sum(h_s > a_s)/n_sims, np.sum(h_s == a_s)/n_sims, np.sum(h_s < a_s)/n_sims
    ov25 = np.sum((h_s + a_s) > 2.5)/n_sims
    he, de, ae = hp-(1/h_o), dp-(1/d_o), ap-(1/a_o)
    
    recs = []
    # 超低門檻觸發，拒絕「觀察中」
    if he > 0.015: recs.append("🏠 主勝推")
    if ae > 0.015: recs.append("🚀 客勝推")
    if de > 0.025: recs.append("💎 和局博弈")
    if ov25 > 0.50: recs.append("🔥 大 2.5")
    elif ov25 < 0.42: recs.append("🛡️ 小 2.5")
    
    # 模擬波膽
    results = [f"{h}:{a}" for h, a in zip(h_s[:2000], a_s[:2000])]
    scores = pd.Series(results).value_counts(normalize=True).head(3)
    
    return he, de, ae, recs, bias, scores

# ==========================================
# 🖥️ 5. 實戰主流程
# ==========================================
def main():
    st.markdown("<h1 style='text-align:center; color:#00ff88;'>🛡️ ZEUS PREDICT PRO v49.0</h1>", unsafe_allow_html=True)
    
    try:
        API_URL = f"https://api.the-odds-api.com/v4/sports/soccer/odds/?apiKey={st.secrets['ODDS_API_KEY']}&regions=eu&markets=h2h"
        data = requests.get(API_URL).json()
    except:
        st.error("❌ API 連接失敗，請檢查金鑰。")
        return

    tab1, tab2 = st.tabs(["🎯 實戰分析中心", "📚 歷史紀錄"])

    with tab1:
        if not data or not isinstance(data, list):
            st.warning("⚠️ 暫無即時數據")
        else:
            for m in data[:20]:
                try:
                    # 時間處理
                    start = datetime.strptime(m['commence_time'], "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=8)
                    time_str = start.strftime("%m/%d %H:%M")
                    
                    market = m['bookmakers'][0]['markets'][0]['outcomes']
                    h_o = next(o['price'] for o in market if o['name'] == m['home_team'])
                    d_o = next(o['price'] for o in market if o['name'] == 'Draw')
                    a_o = next(o['price'] for o in market if o['name'] == m['away_team'])
                    
                    he, de, ae, recs, bias, scores = run_simulation(h_o, d_o, a_o, m['sport_title'])

                    # 建立標籤 HTML
                    score_tags = "".join([f"<div class='score-badge'>{s} ({p:.1%})</div>" for s, p in scores.items()])
                    rec_tags = "".join([f"<div class='rec-badge'>{r}</div>" for r in recs]) if recs else "<span style='color:#6e7681;'>模型分析中...</span>"

                    # 重要：移除所有 Markdown 可能誤判的縮進
                    card_html = f"""<div class="master-card">
<div style="display:flex; justify-content:space-between; align-items:center;">
<span style="color:#8b949e; font-size:0.85rem;">🏆 {m['sport_title']} | {bias['label']}</span>
<span class="time-tag">🕒 開賽：{time_str}</span>
</div>
<div class="team-line">
<span style="color:#238636;">[主]</span> {m['home_team']} 
<span style="color:#8b949e; font-size:0.9rem;"> VS </span> 
{m['away_team']} <span style="color:#1f6feb;">[客]</span>
</div>
<div style="margin: 10px 0;">
<span style="color:#8b949e; font-size:0.85rem; margin-right:10px;">🎲 模擬波膽:</span>{score_tags}
</div>
<div style="display:flex; justify-content:space-between; align-items:center; border-top:1px solid #30363d; padding-top:12px; margin-top:10px;">
<div>{rec_tags}</div>
<div class="edge-val">Edge: {max(he, ae, de):+.1%}</div>
</div>
</div>"""
                    st.markdown(card_html, unsafe_allow_html=True)
                except: continue

    with tab2:
        conn = sqlite3.connect('zeus_data.db')
        df = pd.read_sql_query("SELECT * FROM matches ORDER BY start_time DESC LIMIT 40", conn)
        st.dataframe(df, use_container_width=True)
        conn.close()

if __name__ == "__main__":
    main()
