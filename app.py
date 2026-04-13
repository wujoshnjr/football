import streamlit as st
import requests
import numpy as np
import pandas as pd
import sqlite3
from datetime import datetime, timedelta

# ==========================================
# 🔑 1. 初始化資料庫 (確保包含 start_time 欄位)
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
# 🧠 2. 聯賽真實數據標籤 (回歸平衡與理性)
# ==========================================
LEAGUE_BIAS = {
    "Premier League": {"adj": 1.05, "label": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 英超"},
    "La Liga": {"adj": 0.95, "label": "🇪🇸 西甲"},
    "Serie A": {"adj": 0.92, "label": "🇮🇹 意甲"},
    "Bundesliga": {"adj": 1.15, "label": "🇩🇪 德甲"},
    "Ligue 1": {"adj": 0.98, "label": "🇫🇷 法甲"},
    "Premier League - Russia": {"adj": 0.85, "label": "❄️ 俄超 (偏小)"}
}

# ==========================================
# 🎨 3. UI 視覺與 CSS 全局配置
# ==========================================
st.set_page_config(page_title="ZEUS PRO v52.0", layout="wide")

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
    .edge-val { color: #00ff88; font-weight: 700; font-size: 0.85rem; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# ⚙️ 4. 核心演算引擎 (10萬次泊松分佈模擬)
# ==========================================
def run_simulation(h_o, d_o, a_o, league_name, n_sims=100000):
    bias = LEAGUE_BIAS.get(league_name, {"adj": 1.0, "label": "⚽ 常規"})
    
    # 1. 還原真實機率 (去除莊家水錢)
    margin = (1/h_o) + (1/d_o) + (1/a_o)
    prob_h, prob_d, prob_a = (1/h_o)/margin, (1/d_o)/margin, (1/a_o)/margin
    
    # 2. 期望總進球數 (依據真實五大聯賽均值約 2.65 設定)
    total_exp_goals = 2.65 * bias['adj']
    
    # 3. 實力分配 (不使用誇張冪次，回歸合理和局機率)
    h_l = total_exp_goals * (prob_h / (prob_h + prob_a)) * 1.05
    a_l = total_exp_goals * (prob_a / (prob_h + prob_a)) * 0.95
    
    # 4. 執行模擬
    h_s = np.random.poisson(h_l, n_sims)
    a_s = np.random.poisson(a_l, n_sims)
    
    # 5. 結果統計
    sim_h_win = np.sum(h_s > a_s) / n_sims
    sim_draw = np.sum(h_s == a_s) / n_sims
    sim_a_win = np.sum(h_s < a_s) / n_sims
    sim_ov25 = np.sum((h_s + a_s) > 2.5) / n_sims
    
    # 6. 優勢計算 (Edge)
    h_edge = sim_h_win - (1/h_o)
    d_edge = sim_draw - (1/d_o)
    a_edge = sim_a_win - (1/a_o)
    
    # 7. 決策推薦 (嚴格門檻，避免每場都無腦推薦)
    recs = []
    if h_edge > 0.03: recs.append("🏠 主勝")
    if a_edge > 0.03: recs.append("🚀 客勝")
    if d_edge > 0.03: recs.append("🤝 和局博弈")
    
    if sim_ov25 > 0.58: recs.append("🔥 大 2.5")
    elif sim_ov25 < 0.42: recs.append("🛡️ 小 2.5")
    
    # 取前三高機率的波膽
    results = [f"{h}:{a}" for h, a in zip(h_s[:5000], a_s[:5000])]
    scores = pd.Series(results).value_counts(normalize=True).head(3)
    
    return h_edge, d_edge, a_edge, recs, bias, scores

# ==========================================
# 🖥️ 5. 實戰主流程 (分頁顯示與自動寫入)
# ==========================================
def main():
    st.markdown("<h1 style='text-align:center; color:#00ff88; font-weight:900;'>🛡️ ZEUS PREDICT PRO v52.0</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center; color:#8b949e; margin-bottom:30px;'>100,000次泊松模擬 | 數據平衡校準版</p>", unsafe_allow_html=True)
    
    # 呼叫 Odds API
    try:
        API_URL = f"https://api.the-odds-api.com/v4/sports/soccer/odds/?apiKey={st.secrets['ODDS_API_KEY']}&regions=eu&markets=h2h"
        data = requests.get(API_URL).json()
    except Exception as e:
        st.error("❌ API 獲取失敗，請確認你的 Streamlit Secrets 是否正確設定 ODDS_API_KEY。")
        return

    # 建立雙頁籤
    tab1, tab2 = st.tabs(["🎯 實戰預測中心", "📚 歷史數據覆盤"])

    with tab1:
        if not data or not isinstance(data, list):
            st.warning("⚠️ 目前暫無即時比賽數據。")
        else:
            for m in data[:20]:
                try:
                    # 時間處理 (轉為台灣時間 UTC+8)
                    start_time = datetime.strptime(m['commence_time'], "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=8)
                    time_str = start_time.strftime("%m/%d %H:%M")
                    
                    # 擷取賠率
                    market = m['bookmakers'][0]['markets'][0]['outcomes']
                    h_o = next(o['price'] for o in market if o['name'] == m['home_team'])
                    d_o = next(o['price'] for o in market if o['name'] == 'Draw')
                    a_o = next(o['price'] for o in market if o['name'] == m['away_team'])
                    
                    # 執行運算
                    he, de, ae, recs, bias, scores = run_simulation(h_o, d_o, a_o, m['sport_title'])

                    # 自動寫入資料庫 (以比賽ID+日期防重複)
                    conn = sqlite3.connect('zeus_data.db')
                    c = conn.cursor()
                    m_id = f"{m['id']}_{start_time.strftime('%Y%m%d')}"
                    pred_str = " ".join(recs) if recs else "數據觀望中"
                    c.execute("INSERT OR IGNORE INTO matches (match_id, league, home, away, prediction, timestamp, start_time) VALUES (?,?,?,?,?,?,?)",
                              (m_id, m['sport_title'], m['home_team'], m['away_team'], pred_str, datetime.now().strftime('%Y-%m-%d %H:%M'), time_str))
                    conn.commit()
                    conn.close()

                    # 建立視覺化標籤
                    score_tags = "".join([f"<div class='score-badge'>{s} ({p:.1%})</div>" for s, p in scores.items()])
                    rec_tags = "".join([f"<div class='rec-badge'>{r}</div>" for r in recs]) if recs else "<span style='color:#4b5563;'>數據觀望中...</span>"

                    # 渲染 HTML (強制靠左無縮進，防 Streamlit 誤判為 Code Block)
                    card_html = f"""<div class="master-card">
<div style="display:flex; justify-content:space-between; font-size:0.8rem; color:#8b949e;">
<span>🏆 {m['sport_title']} | {bias['label']}</span>
<span>🕒 {time_str}</span>
</div>
<div class="team-line">
{m['home_team']} <span style="color:#444; font-size:0.9rem;">vs</span> {m['away_team']}
</div>
<div style="margin: 10px 0;">
<span style="color:#8b949e; font-size:0.85rem; margin-right:8px;">🎯 高勝率波膽:</span>
{score_tags}
</div>
<div style="display:flex; justify-content:space-between; align-items:center; border-top:1px solid #30363d; padding-top:10px;">
<div>{rec_tags}</div>
<div class="edge-val">優勢 Edge: {max(he, de, ae):+.1%}</div>
</div>
</div>"""
                    st.markdown(card_html, unsafe_allow_html=True)
                except Exception as e:
                    continue

    with tab2:
        st.markdown("### 📝 賽果覆盤編輯器")
        st.write("直接在下方表格修改「真實賽果」與「狀態」，並點擊最下方按鈕進行儲存更新。")
        
        conn = sqlite3.connect('zeus_data.db')
        df = pd.read_sql_query("SELECT match_id, start_time, league, home, away, prediction, result, status FROM matches ORDER BY start_time DESC LIMIT 50", conn)
        
        if not df.empty:
            # 建立可編輯資料表
            edited_df = st.data_editor(
                df,
                column_config={
                    "match_id": None, # 隱藏系統 ID
                    "start_time": "開賽時間",
                    "league": "聯賽",
                    "home": "主隊",
                    "away": "客隊",
                    "prediction": "系統推薦",
                    "result": st.column_config.TextColumn("真實賽果", help="請輸入完賽比分，如 2:1"),
                    "status": st.column_config.SelectboxColumn(
                        "預測狀態", 
                        options=["待定", "✅ 命中", "❌ 未中", "➖ 走水"],
                        help="選擇此單的派彩結果"
                    )
                },
                disabled=["start_time", "league", "home", "away", "prediction"], # 防止修改核心數據
                use_container_width=True,
                hide_index=True
            )
            
            # 儲存更新機制
            if st.button("💾 儲存並更新覆盤結果", use_container_width=True):
                c = conn.cursor()
                for index, row in edited_df.iterrows():
                    c.execute("UPDATE matches SET result=?, status=? WHERE match_id=?", 
                              (row['result'], row['status'], row['match_id']))
                conn.commit()
                st.success("✅ 歷史紀錄已成功更新！")
        else:
            st.info("💡 目前資料庫中還沒有歷史數據，預測中心的賽事會自動寫入此處。")
            
        conn.close()

if __name__ == "__main__":
    main()
