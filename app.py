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
    conn.close()

init_db()

# ==========================================
# 🧠 2. 聯賽真實數據修正 (回歸理性)
# ==========================================
LEAGUE_BIAS = {
    "Premier League": {"adj": 1.05, "label": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 英超"},
    "La Liga": {"adj": 0.95, "label": "🇪🇸 西甲"},
    "Serie A": {"adj": 0.92, "label": "🇮🇹 意甲"},
    "Bundesliga": {"adj": 1.15, "label": "🇩🇪 德甲"},
    "Ligue 1": {"adj": 0.98, "label": "🇫🇷 法甲"},
    "Premier League - Russia": {"adj": 0.85, "label": "❄️ 俄超(偏小)"}
}

# ==========================================
# 🎨 3. UI 視覺配置
# ==========================================
st.set_page_config(page_title="ZEUS PRO v50.0", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0d1117; color: #e6edf3; }
    .master-card {
        background: #161b22; border: 1px solid #30363d; border-radius: 12px;
        padding: 20px; margin-bottom: 20px; border-left: 5px solid #00ff88;
    }
    .team-line { font-size: 1.25rem; font-weight: 700; margin: 10px 0; color: #ffffff; }
    .score-badge { background: #21262d; color: #58a6ff; padding: 4px 10px; border-radius: 5px; font-size: 0.9rem; border: 1px solid #30363d; margin-right: 8px; display: inline-block; font-family: monospace; }
    .rec-badge { background: #f1c40f; color: #000; padding: 5px 12px; border-radius: 6px; font-weight: 800; margin-right: 8px; display: inline-block; font-size: 0.85rem; }
    .edge-val { color: #00ff88; font-weight: 700; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# ⚙️ 4. 核心演算引擎 (10萬次真實數據模擬)
# ==========================================
def run_simulation(h_o, d_o, a_o, league_name, n_sims=100000):
    bias = LEAGUE_BIAS.get(league_name, {"adj": 1.0, "label": "⚽ 常規"})
    
    # 1. 移除莊家抽水，計算公平機率
    margin = (1/h_o) + (1/d_o) + (1/a_o)
    prob_h, prob_d, prob_a = (1/h_o)/margin, (1/d_o)/margin, (1/a_o)/margin
    
    # 2. 根據真實足球數據設定進球期望值 (平均約 2.65 球)
    total_exp_goals = 2.65 * bias['adj']
    
    # 3. 根據勝平負機率逆推主客隊 Lambda (考慮和局的可能性)
    # 使用簡單的實力權重分配，不再過度拉開差距
    h_l = total_exp_goals * (prob_h / (prob_h + prob_a)) * 1.05
    a_l = total_exp_goals * (prob_a / (prob_h + prob_a)) * 0.95
    
    # 4. 執行 100,000 場模擬
    h_s = np.random.poisson(h_l, n_sims)
    a_s = np.random.poisson(a_l, n_sims)
    
    # 5. 統計模擬結果
    sim_h_win = np.sum(h_s > a_s) / n_sims
    sim_draw = np.sum(h_s == a_s) / n_sims
    sim_a_win = np.sum(h_s < a_s) / n_sims
    sim_ov25 = np.sum((h_s + a_s) > 2.5) / n_sims
    
    # 6. 計算 Edge (模擬機率 vs 莊家機率)
    h_edge = sim_h_win - (1/h_o)
    d_edge = sim_draw - (1/d_o)
    a_edge = sim_a_win - (1/a_o)
    
    recs = []
    # 嚴格篩選真正有價值的選擇
    if h_edge > 0.03: recs.append("🏠 主勝")
    if a_edge > 0.03: recs.append("🚀 客勝")
    if d_edge > 0.03: recs.append("🤝 和局建議")
    
    # 大小分判定 (回歸理性門檻)
    if sim_ov25 > 0.58: recs.append("🔥 大 2.5")
    elif sim_ov25 < 0.42: recs.append("🛡️ 小 2.5")
    
    # 提取前 3 名高機率波膽
    results = [f"{h}:{a}" for h, a in zip(h_s[:5000], a_s[:5000])]
    scores = pd.Series(results).value_counts(normalize=True).head(3)
    
    return h_edge, d_edge, a_edge, recs, bias, scores

# ==========================================
# 🖥️ 5. 實戰主流程
# ==========================================
def main():
    st.markdown("<h2 style='text-align:center; color:#00ff88;'>🛡️ ZEUS PREDICT PRO v50.0</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center; color:#8b949e;'>100,000次泊松模擬 | 數據平衡校準版</p>", unsafe_allow_html=True)
    
    try:
        API_URL = f"https://api.the-odds-api.com/v4/sports/soccer/odds/?apiKey={st.secrets['ODDS_API_KEY']}&regions=eu&markets=h2h"
        data = requests.get(API_URL).json()
    except:
        st.error("API 獲取失敗")
        return

    if not data or not isinstance(data, list):
        st.warning("目前暫無比賽數據")
        return

    for m in data[:20]:
        try:
            start_time = datetime.strptime(m['commence_time'], "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=8)
            time_str = start_time.strftime("%m/%d %H:%M")
            
            market = m['bookmakers'][0]['markets'][0]['outcomes']
            h_o = next(o['price'] for o in market if o['name'] == m['home_team'])
            d_o = next(o['price'] for o in market if o['name'] == 'Draw')
            a_o = next(o['price'] for o in market if o['name'] == m['away_team'])
            
            he, de, ae, recs, bias, scores = run_simulation(h_o, d_o, a_o, m['sport_title'])

            # 建立波膽標籤
            score_tags = "".join([f"<div class='score-badge'>{s} ({p:.1%})</div>" for s, p in scores.items()])
            rec_tags = "".join([f"<div class='rec-badge'>{r}</div>" for r in recs]) if recs else "<span style='color:#4b5563;'>數據觀望中</span>"

            st.markdown(f"""
            <div class="master-card">
                <div style="display:flex; justify-content:space-between; font-size:0.8rem; color:#8b949e;">
                    <span>🏆 {m['sport_title']} | {bias['label']}</span>
                    <span>🕒 {time_str}</span>
                </div>
                <div class="team-line">
                    {m['home_team']} <span style="color:#444;">vs</span> {m['away_team']}
                </div>
                <div style="margin: 10px 0;">
                    <span style="color:#8b949e; font-size:0.8rem; margin-right:8px;">🎯 模擬高勝率波膽:</span>
                    {score_tags}
                </div>
                <div style="display:flex; justify-content:space-between; align-items:center; border-top:1px solid #30363d; padding-top:10px;">
                    <div>{rec_tags}</div>
                    <div class="edge-val" style="font-size:0.85rem;">優勢 Edge: {max(he, de, ae):+.1%}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        except:
            continue

if __name__ == "__main__":
    main()
