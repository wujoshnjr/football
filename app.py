import streamlit as st
import requests
import numpy as np
import pandas as pd
import sqlite3
import pytz
from datetime import datetime
from scipy.stats import poisson
from scipy.optimize import root_scalar

# ==========================================
# 🔑 1. 初始化資料庫 (加入 UPSERT 支援)
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
# ⚡ 2. 數據抓取引擎 (抓取 H2H + Totals)
# ==========================================
@st.cache_data(ttl=600)
def fetch_odds_data(api_key):
    # 抓取獨贏與大小球市場
    url = f"https://api.the-odds-api.com/v4/sports/soccer/odds/?apiKey={api_key}&regions=eu&markets=h2h,totals"
    try:
        response = requests.get(url)
        return response.status_code, response.json(), response.headers
    except Exception as e:
        return 500, str(e), {}

# ==========================================
# 🧠 3. 專業量化核心 (PMF + 動態進球反推)
# ==========================================
def solve_implied_total_goals(p_under25):
    """利用博彩公司的小球機率，反推隱含的預期總進球數 (T)"""
    def obj(T): 
        return poisson.cdf(2, T) - p_under25
    try:
        # 在 0.1 到 8.0 顆進球的合理區間內尋找數值解
        res = root_scalar(obj, bracket=[0.1, 8.0], method='brentq')
        return res.root
    except:
        return 2.65 # 解算失敗時的保守退路

def run_quant_model(h_odds, d_odds, a_odds, o25_odds, u25_odds):
    # 1. 消除莊家抽水 (Margin) 獲取真實隱含機率
    margin_1x2 = (1/h_odds) + (1/d_odds) + (1/a_odds)
    p_h, p_d, p_a = (1/h_odds)/margin_1x2, (1/d_odds)/margin_1x2, (1/a_odds)/margin_1x2
    
    margin_totals = (1/o25_odds) + (1/u25_odds) if o25_odds and u25_odds else 1.0
    p_u25 = (1/u25_odds)/margin_totals if u25_odds else 0.48
    
    # 2. 反推總進球數 T
    T = solve_implied_total_goals(p_u25)
    
    # 3. 將 T 分配給主客隊 (加入 Dixon-Coles 精神的非線性壓縮)
    # 不直接用勝率比，而是適度平滑，反映強隊「防守也強」的特性
    ratio = p_h / p_a
    lambda_h = T * (ratio**0.7 / (ratio**0.7 + 1))
    lambda_a = T - lambda_h
    
    # 4. 建立 10x10 的精確泊松機率矩陣
    max_g = 10
    x, y = np.arange(max_g), np.arange(max_g)
    pmf_h = poisson.pmf(x, lambda_h)
    pmf_a = poisson.pmf(y, lambda_a)
    prob_matrix = np.outer(pmf_h, pmf_a)
    
    # 5. 計算模型機率
    model_h = np.sum(np.tril(prob_matrix, -1))
    model_d = np.sum(np.diag(prob_matrix))
    model_a = np.sum(np.triu(prob_matrix, 1))
    model_o25 = 1 - np.sum(prob_matrix[:3, :3][np.triu_indices(3)] + prob_matrix[1:3, 0] + [prob_matrix[2,1]]*0) # 簡化寫法，精確算法如下：
    
    model_u25 = 0
    for i in range(3):
        for j in range(3-i):
            model_u25 += prob_matrix[i, j]
    model_o25 = 1 - model_u25

    # 6. Edge 判定 (提高標準至 2.5% 以上)
    edge_h, edge_d, edge_a = model_h - p_h, model_d - p_d, model_a - p_a
    
    recs = []
    # 足球市場高效，設定嚴謹的 2.5% Edge 門檻
    if edge_h > 0.025: recs.append("🏠 主勝價值")
    if edge_a > 0.025: recs.append("🚀 客勝價值")
    if edge_d > 0.025: recs.append("🤝 和局博弈")
    
    # 大小球判定
    if o25_odds and (model_o25 - (1/o25_odds)/margin_totals > 0.03): recs.append("🔥 大 2.5")
    elif u25_odds and (model_u25 - p_u25 > 0.03): recs.append("🛡️ 小 2.5")
    
    # 提取波膽 Top 3
    scores = {}
    flat_indices = np.argsort(prob_matrix, axis=None)[::-1][:3]
    for idx in flat_indices:
        r, c = np.unravel_index(idx, prob_matrix.shape)
        scores[f"{r}:{c}"] = prob_matrix[r, c]
        
    return edge_h, edge_d, edge_a, recs, scores, T

# ==========================================
# 🎨 4. UI 視覺美化 
# ==========================================
def apply_styles():
    st.markdown("""
    <style>
        .stApp { background-color: #0d1117; color: #e6edf3; }
        .master-card { background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 20px; margin-bottom: 20px; border-left: 6px solid #8a2be2; }
        .team-line { font-size: 1.3rem; font-weight: 800; margin: 12px 0; color: #ffffff; }
        .score-badge { background: #21262d; color: #58a6ff; padding: 4px 10px; border-radius: 5px; font-size: 0.85rem; border: 1px solid #30363d; margin-right: 8px; display: inline-block; font-family: monospace; }
        .rec-badge { background: #f1c40f; color: #000; padding: 6px 14px; border-radius: 8px; font-weight: 900; margin-right: 10px; display: inline-block; }
        .edge-val { color: #00ff88; font-weight: 700; font-family: monospace; }
        .err-msg { color: #ff7b72; font-size: 0.85rem; margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 🖥️ 5. 主程式
# ==========================================
def main():
    apply_styles()
    st.markdown("<h1 style='text-align:center; color:#8a2be2;'>⚛️ ZEUS QUANT PRO v66.0</h1>", unsafe_allow_html=True)
    
    # 使用 pytz 處理台灣時區
    tw_tz = pytz.timezone('Asia/Taipei')
    
    tab1, tab2, tab3 = st.tabs(["🎯 量化預測模型", "📚 歷史覆盤", "⚙️ 系統診斷"])

    try:
        api_key = st.secrets["ODDS_API_KEY"]
    except:
        st.error("❌ 未偵測到 API Key。")
        return

    with tab1:
        status_code, data, headers = fetch_odds_data(api_key)
        remaining = headers.get('x-requests-remaining', 'N/A')
        
        if status_code != 200:
            st.error(f"🚨 API 拒絕存取：{status_code}")
            return

        st.markdown(f"<p style='color:#ffa500; font-family:monospace;'>最後運算：{datetime.now(tw_tz).strftime('%H:%M:%S')} | 💎 API 額度：{remaining}</p>", unsafe_allow_html=True)

        if not data:
            st.warning("⚠️ 目前暫無賽事。")
        else:
            for m in data[:30]:
                try:
                    bm = m.get('bookmakers')
                    if not bm: continue
                    
                    # 擷取 1X2 賠率
                    h2h_market = next((mk for mk in bm[0]['markets'] if mk['key'] == 'h2h'), None)
                    if not h2h_market: continue
                    outcomes = h2h_market['outcomes']
                    h_o = next(o['price'] for o in outcomes if o['name'] == m['home_team'])
                    d_o = next(o['price'] for o in outcomes if o['name'] == 'Draw')
                    a_o = next(o['price'] for o in outcomes if o['name'] == m['away_team'])
                    
                    # 擷取 Totals (大小球) 賠率
                    totals_market = next((mk for mk in bm[0]['markets'] if mk['key'] == 'totals'), None)
                    o25_o, u25_o = None, None
                    if totals_market:
                        t_outcomes = totals_market['outcomes']
                        # 尋找 2.5 球的盤口
                        o25_o = next((o['price'] for o in t_outcomes if o['name'] == 'Over' and o.get('point') == 2.5), None)
                        u25_o = next((o['price'] for o in t_outcomes if o['name'] == 'Under' and o.get('point') == 2.5), None)
                    
                    # 執行量化運算
                    edge_h, edge_d, edge_a, recs, scores, expected_T = run_quant_model(h_o, d_o, a_o, o25_o, u25_o)
                    
                    start_dt = datetime.strptime(m['commence_time'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=pytz.utc).astimezone(tw_tz)
                    time_label = start_dt.strftime("%m/%d %H:%M")

                    # UPSERT: 確保臨場賠率變動會覆蓋舊數據
                    conn = sqlite3.connect('zeus_data.db')
                    c = conn.cursor()
                    m_id = f"{m['id']}_{start_dt.strftime('%m%d')}"
                    pred_txt = " ".join(recs) if recs else "模型無優勢 (No Edge)"
                    
                    c.execute("""
                        INSERT INTO matches (match_id, league, home, away, prediction, status, timestamp, start_time) 
                        VALUES (?,?,?,?,?,?,?,?)
                        ON CONFLICT(match_id) DO UPDATE SET
                        prediction=excluded.prediction,
                        timestamp=excluded.timestamp
                    """, (m_id, m['sport_title'], m['home_team'], m['away_team'], pred_txt, "待定", datetime.now(tw_tz).strftime('%Y-%m-%d %H:%M'), time_label))
                    conn.commit(); conn.close()

                    # 渲染 UI
                    score_html = "".join([f"<div class='score-badge'>{s} ({p:.1%})</div>" for s, p in scores.items()])
                    rec_html = "".join([f"<div class='rec-badge'>{r}</div>" for r in recs]) if recs else "<span style='color:#666;'>無顯著交易價值</span>"
                    
                    st.markdown(f"""<div class="master-card">
                        <div style="display:flex; justify-content:space-between; font-size:0.8rem; color:#8b949e;">
                            <span>🏆 {m['sport_title']} | 預期進球: {expected_T:.2f}</span>
                            <span>🕒 {time_label}</span>
                        </div>
                        <div class="team-line">{m['home_team']} <span style="color:#444;">vs</span> {m['away_team']}</div>
                        <div style="margin: 10px 0;">{score_html}</div>
                        <div style="display:flex; justify-content:space-between; align-items:center; border-top:1px solid #30363d; padding-top:12px;">
                            <div>{rec_html}</div>
                            <div class="edge-val">Max Edge: {max(edge_h, edge_d, edge_a):+.1%}</div>
                        </div>
                    </div>""", unsafe_allow_html=True)
                
                except Exception as e:
                    # 捕捉異常並明確顯示
                    st.markdown(f"<div class='err-msg'>⚠️ 解析賽事 {m.get('home_team', 'Unknown')} 失敗: {str(e)}</div>", unsafe_allow_html=True)
                    continue

    with tab2:
        st.markdown("### 📝 賽果覆盤")
        conn = sqlite3.connect('zeus_data.db')
        df = pd.read_sql_query("SELECT match_id, start_time, league, home, away, prediction, result, status FROM matches ORDER BY timestamp DESC LIMIT 100", conn)
        if not df.empty:
            edited = st.data_editor(df, column_config={
                "match_id": None, "status": st.column_config.SelectboxColumn("狀態", options=["待定", "✅ 命中", "❌ 未中", "➖ 走水"])
            }, use_container_width=True, hide_index=True)
            if st.button("💾 儲存修改內容", use_container_width=True):
                c = conn.cursor()
                for _, r in edited.iterrows():
                    c.execute("UPDATE matches SET result=?, status=? WHERE match_id=?", (r['result'], r['status'], r['match_id']))
                conn.commit(); st.success("更新成功！")
        conn.close()

    with tab3:
        st.markdown("### ⚙️ 系統狀態")
        st.write(f"時區核心：`{tw_tz.zone}`")
        if st.button("🗑️ 清空所有數據"):
            conn = sqlite3.connect('zeus_data.db'); c = conn.cursor()
            c.execute("DELETE FROM matches"); conn.commit(); conn.close()
            st.rerun()

if __name__ == "__main__":
    main()
