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
# 🔑 1. 初始化量化數據庫 (新增球隊戰力記憶體)
# ==========================================
def init_db():
    conn = sqlite3.connect('zeus_quant_v80.db', check_same_thread=False)
    c = conn.cursor()
    # 賽事紀錄表
    c.execute('''CREATE TABLE IF NOT EXISTS matches 
                 (match_id TEXT PRIMARY KEY, league TEXT, home TEXT, away TEXT, 
                  prediction TEXT, result TEXT, status TEXT, timestamp TEXT, start_time TEXT)''')
    # 球隊戰力記憶表 (ELO & 攻防指數)
    c.execute('''CREATE TABLE IF NOT EXISTS team_power 
                 (team_name TEXT PRIMARY KEY, elo REAL, attack REAL, defense REAL)''')
    conn.commit()
    conn.close()

init_db()

# 獲取或初始化球隊戰力
def get_team_power(team_name):
    conn = sqlite3.connect('zeus_quant_v80.db')
    c = conn.cursor()
    c.execute("SELECT elo, attack, defense FROM team_power WHERE team_name=?", (team_name,))
    row = c.fetchone()
    conn.close()
    if row: return row[0], row[1], row[2]
    else: return 1500.0, 1.0, 1.0 # 初始值：Elo 1500, 攻防係數 1.0

# 根據真實賽果更新戰力 (自我學習機制)
def update_team_power(home_team, away_team, h_goals, a_goals):
    h_elo, h_att, h_def = get_team_power(home_team)
    a_elo, a_att, a_def = get_team_power(away_team)
    
    # Elo 更新邏輯 (主場優勢設為 50)
    expected_h = 1 / (1 + 10 ** ((a_elo - (h_elo + 50)) / 400))
    actual_h = 1 if h_goals > a_goals else (0.5 if h_goals == a_goals else 0)
    k_factor = 20 # 學習速率
    
    new_h_elo = h_elo + k_factor * (actual_h - expected_h)
    new_a_elo = a_elo + k_factor * ((1 - actual_h) - (1 - expected_h))
    
    # 攻防指數更新 (微調)
    new_h_att = h_att * 0.95 + (h_goals / 1.5) * 0.05
    new_h_def = h_def * 0.95 + (a_goals / 1.5) * 0.05
    new_a_att = a_att * 0.95 + (a_goals / 1.5) * 0.05
    new_a_def = a_def * 0.95 + (h_goals / 1.5) * 0.05

    conn = sqlite3.connect('zeus_quant_v80.db')
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO team_power VALUES (?, ?, ?, ?)", (home_team, new_h_elo, new_h_att, new_h_def))
    c.execute("INSERT OR REPLACE INTO team_power VALUES (?, ?, ?, ?)", (away_team, new_a_elo, new_a_att, new_a_def))
    conn.commit()
    conn.close()

# ==========================================
# 🧠 2. 量化核心 (融合盤口與資料庫基本面)
# ==========================================

def power_method_probs(odds):
    odds_arr = np.array(odds)
    try:
        def func(k): return np.sum(np.power(1/odds_arr, k)) - 1.0
        res = root_scalar(func, bracket=[0.1, 5.0], method='brentq')
        return np.power(1/odds_arr, res.root) if res.converged else (1/odds_arr)/np.sum(1/odds_arr)
    except: return (1/odds_arr)/np.sum(1/odds_arr)

def apply_dixon_coles(matrix, l_h, l_a, rho=-0.1):
    def tau(x, y, lh, la, r):
        if x==0 and y==0: return 1 - lh*la*r
        if x==0 and y==1: return 1 + lh*r
        if x==1 and y==0: return 1 + la*r
        if x==1 and y==1: return 1 - r
        return 1
    corrected = matrix.copy()
    for i in range(2):
        for j in range(2): corrected[i, j] *= tau(i, j, l_h, l_a, rho)
    return corrected / corrected.sum()

def run_pro_analysis(h_o, d_o, a_o, o25_o, u25_o, home_team, away_team):
    # 1. 盤口去水機率
    p_h_odds, p_d_odds, p_a_odds = power_method_probs([h_o, d_o, a_o])
    p_u25_odds = power_method_probs([o25_o, u25_o])[1] if (o25_o and u25_o) else 0.48
    
    # 2. 獲取資料庫基本面戰力 (ELO & 攻防)
    h_elo, h_att, h_def = get_team_power(home_team)
    a_elo, a_att, a_def = get_team_power(away_team)
    
    # 計算基本面勝率
    p_h_elo = 1 / (1 + 10 ** ((a_elo - (h_elo + 50)) / 400))
    p_a_elo = 1 - p_h_elo - 0.25 # 粗估和局佔 25%
    
    # 3. 盤口與基本面融合 (Bayesian Blending)
    p_h = p_h_odds * 0.7 + p_h_elo * 0.3
    p_a = p_a_odds * 0.7 + p_a_elo * 0.3
    
    # 4. 計算預期總進球與攻防分配
    try: T = root_scalar(lambda x: poisson.cdf(2, x) - p_u25_odds, bracket=[0.1, 8.0]).root
    except: T = 2.65
    
    # 加入球隊攻擊防守係數調整
    ratio = (p_h / p_a) * (h_att / a_def) * (a_att / h_def)
    l_h = T * (ratio**0.72 / (ratio**0.72 + 1))
    l_a = T - l_h
    
    # 5. 生成 6x6 波膽矩陣
    matrix = apply_dixon_coles(np.outer(poisson.pmf(np.arange(6), l_h), poisson.pmf(np.arange(6), l_a)), l_h, l_a)
    
    # 6. 進階市場機率計算
    m_h, m_d, m_a = np.sum(np.tril(matrix, -1)), np.sum(np.diag(matrix)), np.sum(np.triu(matrix, 1))
    m_o25 = 1 - np.sum([matrix[i, j] for i in range(3) for j in range(3-i)])
    m_u25 = 1 - m_o25
    
    # 特殊玩法機率
    btts_yes = 1 - np.sum(matrix[0,:]) - np.sum(matrix[:,0]) + matrix[0,0] # 雙方皆進球
    dnb_h = m_h / (m_h + m_a) # 平手退款(主)
    dc_1x = m_h + m_d # 雙勝彩(主或和)
    
    # 7. 尋找終極價值與推薦
    markets = [("主勝(1)", m_h, h_o), ("和局(X)", m_d, d_o), ("客勝(2)", m_a, a_o), ("大 2.5", m_o25, o25_o), ("小 2.5", m_u25, u25_o)]
    best_edge, recommendation = 0, "⚠️ 市場極度高效，建議觀望或小注娛樂"
    
    for label, prob, odds in markets:
        if odds and odds > 1.0:
            edge = prob - (1/odds)
            if edge > best_edge and edge > 0.02:
                best_edge = edge
                stars = "⭐" * int(min(5, (edge/0.02)))
                recommendation = f"🔥 最佳玩法：{label} | 優勢: +{edge:.1%} | 信心: {stars}"
    
    # 波膽 Top 3
    scores = {f"{r}:{c}": matrix[r, c] for r, c in zip(*np.unravel_index(np.argsort(matrix, axis=None)[::-1][:3], matrix.shape))}
    
    adv_stats = {"BTTS": btts_yes, "DNB_H": dnb_h, "DC_1X": dc_1x, "H_ELO": h_elo, "A_ELO": a_elo}
    return m_h, m_d, m_a, recommendation, scores, T, adv_stats

# ==========================================
# 🖥️ 3. UI 介面與深度渲染
# ==========================================
def main():
    st.set_page_config(page_title="ZEUS QUANT v80", layout="wide")
    tw_tz = pytz.timezone('Asia/Taipei')
    
    st.markdown("""
    <style>
        .stApp { background-color: #0b0f19; color: #e2e8f0; }
        .stat-box { background: #1e293b; padding: 10px; border-radius: 8px; text-align: center; border: 1px solid #334155; }
        .stat-title { font-size: 0.8rem; color: #94a3b8; }
        .stat-val { font-size: 1.2rem; font-weight: bold; color: #38bdf8; }
        .score-badge { background: #0f172a; color: #10b981; padding: 4px 10px; border-radius: 4px; font-family: monospace; border: 1px solid #059669; margin-right:5px;}
    </style>
    """, unsafe_allow_html=True)

    st.markdown("<h1 style='text-align:center; color:#38bdf8;'>⚛️ ZEUS QUANT TERMINAL v80.0</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center; color:#94a3b8;'>內建 ELO 戰力記憶體 · 全市場深度解析</p>", unsafe_allow_html=True)

    try: api_key = st.secrets["ODDS_API_KEY"]
    except: st.error("🔑 請設定 ODDS_API_KEY"); return

    tab1, tab2 = st.tabs(["🎯 賽事情報與預測", "📚 戰力資料庫與學習中心"])

    with tab1:
        # 搜尋列
        search_query = st.text_input("🔍 搜尋球隊或聯賽 (例如: Arsenal, Premier League)", "")
        
        url = f"https://api.the-odds-api.com/v4/sports/soccer/odds/?apiKey={api_key}&regions=eu&markets=h2h,totals"
        res = requests.get(url)
        if res.status_code != 200: st.error("API 請求失敗"); return
        
        data = res.json()
        st.caption(f"數據庫連線正常 | 最後更新: {datetime.now(tw_tz).strftime('%H:%M:%S')}")

        for m in data:
            # 搜尋過濾
            if search_query.lower() not in m['sport_title'].lower() and search_query.lower() not in m['home_team'].lower() and search_query.lower() not in m['away_team'].lower():
                continue

            try:
                bm = m['bookmakers'][0]['markets']
                h2h = next(mk for mk in bm if mk['key'] == 'h2h')
                totals = next((mk for mk in bm if mk['key'] == 'totals'), None)
                
                h_o = next(o['price'] for o in h2h['outcomes'] if o['name'] == m['home_team'])
                d_o = next(o['price'] for o in h2h['outcomes'] if o['name'] == 'Draw')
                a_o = next(o['price'] for o in h2h['outcomes'] if o['name'] == m['away_team'])
                
                o25_o = next((o['price'] for o in totals['outcomes'] if o['name'] == 'Over' and o.get('point') == 2.5), 2.0) if totals else 2.0
                u25_o = next((o['price'] for o in totals['outcomes'] if o['name'] == 'Under' and o.get('point') == 2.5), 2.0) if totals else 2.0

                start_time = datetime.strptime(m['commence_time'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=pytz.utc).astimezone(tw_tz)
                
                # 執行深度分析
                m_h, m_d, m_a, recommendation, scores, T, adv = run_pro_analysis(h_o, d_o, a_o, o25_o, u25_o, m['home_team'], m['away_team'])

                # UI: 摺疊面板 (Expander) 取代原本擁擠的卡片
                with st.expander(f"🏆 {m['sport_title']} | {m['home_team']} VS {m['away_team']} | 🕒 {start_time.strftime('%m/%d %H:%M')}"):
                    
                    st.success(recommendation) # 明確的下注建議
                    
                    # 核心機率與比分
                    st.markdown("##### 📊 核心預測分析")
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("🏠 主勝機率", f"{m_h:.1%}", f"賠率: {h_o}")
                    col2.metric("🤝 和局機率", f"{m_d:.1%}", f"賠率: {d_o}")
                    col3.metric("🚀 客勝機率", f"{m_a:.1%}", f"賠率: {a_o}")
                    col4.metric("⚽ 預期總進球", f"{T:.2f} 球")

                    score_str = " ".join([f"<span class='score-badge'>{s} ({p:.1%})</span>" for s, p in scores.items()])
                    st.markdown(f"**Top 3 波膽預測：** {score_str}", unsafe_allow_html=True)
                    
                    st.markdown("---")
                    # 深度數據分析
                    st.markdown("##### 🧠 深度衍生市場 & 戰力情報")
                    sub_col1, sub_col2, sub_col3 = st.columns(3)
                    with sub_col1:
                        st.markdown(f"<div class='stat-box'><div class='stat-title'>雙方皆進球 (BTTS)</div><div class='stat-val'>{adv['BTTS']:.1%}</div></div>", unsafe_allow_html=True)
                    with sub_col2:
                        st.markdown(f"<div class='stat-box'><div class='stat-title'>主隊平手退款 (DNB)</div><div class='stat-val'>{adv['DNB_H']:.1%}</div></div>", unsafe_allow_html=True)
                    with sub_col3:
                        st.markdown(f"<div class='stat-box'><div class='stat-title'>主隊雙勝彩 (1X)</div><div class='stat-val'>{adv['DC_1X']:.1%}</div></div>", unsafe_allow_html=True)
                    
                    st.caption(f"🤖 系統戰力記憶：主隊 ELO {adv['H_ELO']:.0f} | 客隊 ELO {adv['A_ELO']:.0f} *(輸入賽果可讓系統進化)*")
                    
                    # 自動記錄到未結算資料庫
                    conn = sqlite3.connect('zeus_quant_v80.db')
                    m_id = f"{m['id']}_{start_time.strftime('%m%d')}"
                    conn.execute("INSERT OR IGNORE INTO matches VALUES (?,?,?,?,?,?,?,?,?)", 
                                (m_id, m['sport_title'], m['home_team'], m['away_team'], recommendation, "", "待定", datetime.now(tw_tz).strftime('%m/%d %H:%M'), start_time.strftime('%m/%d %H:%M')))
                    conn.commit(); conn.close()
                    
            except Exception as e: continue

    with tab2:
        st.markdown("### 📚 歷史覆盤與自我學習中心")
        st.info("💡 **操作指南**：在這裡輸入真實的完場比分。系統會根據賽果，自動修正球隊在數據庫中的「攻擊」、「防禦」與「ELO」數值。你的每一次輸入，都會讓模型變得更精準！")
        
        conn = sqlite3.connect('zeus_quant_v80.db')
        df = pd.read_sql_query("SELECT match_id, start_time as '開賽時間', home as '主隊', away as '客隊', result as '真實比分(例如2:1)' FROM matches ORDER BY timestamp DESC LIMIT 50", conn)
        
        edited_df = st.data_editor(df, disabled=["match_id", "開賽時間", "主隊", "客隊"], use_container_width=True, hide_index=True)
        
        if st.button("💾 儲存比分並訓練模型", use_container_width=True):
            c = conn.cursor()
            for _, row in edited_df.iterrows():
                new_result = row['真實比分(例如2:1)']
                # 如果使用者填寫了比分 (例如 2:1)
                if new_result and ":" in str(new_result):
                    try:
                        hg, ag = map(int, new_result.split(":"))
                        c.execute("UPDATE matches SET result=?, status='已結算' WHERE match_id=?", (new_result, row['match_id']))
                        # 核心學習機制：更新球隊戰力
                        update_team_power(row['主隊'], row['客隊'], hg, ag)
                    except: pass
            conn.commit()
            st.success("✅ 數據庫已更新，模型戰力評估已自我進化！")
        conn.close()

if __name__ == "__main__":
    main()
